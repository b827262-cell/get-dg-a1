#!/usr/bin/env python3
"""Manual test for log sources implementation."""

import tempfile
from pathlib import Path

from backend.services.log_sources import LogSourcesService


def main():
    """Test log sources implementation manually."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"

        # Run migrations
        migrations_dir = Path(__file__).parent / "secmon-linux-security" / "database" / "migrations"
        from database.migrate import migrate

        print("Running migrations...")
        migrate(db_path, migrations_dir)

        # Test log sources service
        print("\n=== Testing Log Sources Service ===\n")

        service = LogSourcesService(db_path)

        # Test 1: Create default log sources
        print("Test 1: Creating default log sources...")
        service.ensure_default_log_sources_exist()
        sources = service.get_all_log_sources()
        print(f"Found {len(sources)} log sources:")
        for source in sources:
            print(f"  - {source.name} (ID: {source.id}, path: {source.device_path})")

        # Test 2: Create a custom log source
        print("\nTest 2: Creating custom log source...")
        custom_id = service.create_log_source(
            name="Custom SSH",
            device_path="/var/log/custom_ssh.log",
            parser_type="ssh",
            status="active",
        )
        print(f"Created custom log source with ID: {custom_id}")

        # Test 3: Get by name
        print("\nTest 3: Getting log source by name...")
        custom_source = service.get_log_source_by_name("Custom SSH")
        print(f"Found: {custom_source.name} (ID: {custom_source.id})")

        # Test 4: Update log source
        print("\nTest 4: Updating log source...")
        success = service.update_log_source(
            custom_id,
            name="Updated Custom SSH",
            status="inactive",
        )
        print(f"Update successful: {success}")

        updated = service.get_log_source(custom_id)
        print(f"After update: {updated.name} (status: {updated.status})")

        # Test 5: Set last scanned
        print("\nTest 5: Setting last scanned timestamp...")
        test_time = "2024-07-10T12:30:45"
        success = service.set_last_scanned(custom_id, test_time)
        print(f"Set last scanned: {success}")

        # Test 6: Delete log source
        print("\nTest 6: Deleting log source...")
        success = service.delete_log_source(custom_id)
        print(f"Delete successful: {success}")

        # Verify deletion
        remaining = service.get_all_log_sources()
        print(f"Remaining log sources: {len(remaining)}")

        print("\n=== All Tests Completed Successfully ===\n")


if __name__ == "__main__":
    main()
