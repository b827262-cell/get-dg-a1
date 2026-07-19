/** SecMon P3 console.  Bearer credentials deliberately live only in memory. */

export const appName = "SecMon";

type Role = "admin" | "analyst" | "viewer";
type User = { id: number; username: string; display_name: string | null; role: Role };
type Summary = {
  events: number;
  attackers: number;
  high_risk: number;
  latest_event_at: string | null;
  read_only_block_count: number;
  log_source_health: Record<string, number>;
};
type EventItem = {
  id: number;
  detected_at: string;
  src_ip: string;
  attack_type: string;
  severity: number;
};
type Attacker = { src_ip: string; total_events: number; threat_score: number; status: string };
type ApiError = Error & { status?: number };

const root = document.getElementById("app") ?? document.body;
let token: string | null = null;
let currentUser: User | null = null;

function element<K extends keyof HTMLElementTagNameMap>(tag: K, text?: string): HTMLElementTagNameMap[K] {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  return node;
}

function clear() {
  root.replaceChildren();
}

function apiPath(path: string) {
  return `/api/v1${path}`;
}

async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body) headers.set("Content-Type", "application/json");
  const response = await fetch(apiPath(path), { ...init, headers });
  if (!response.ok) {
    const error = new Error(response.status === 401 ? "Your session has expired. Please sign in again." : "The request could not be completed.") as ApiError;
    error.status = response.status;
    if (response.status === 401) {
      token = null;
      currentUser = null;
    }
    throw error;
  }
  return response.status === 204 ? (undefined as T) : (response.json() as Promise<T>);
}

function navigate(path: "login" | "dashboard" | "admin") {
  location.hash = `#/${path}`;
}

function message(text: string, kind: "error" | "notice" = "notice") {
  const node = element("p", text);
  node.setAttribute("role", kind === "error" ? "alert" : "status");
  node.className = kind;
  return node;
}

function renderShell(title: string) {
  clear();
  const header = element("header");
  header.append(element("h1", appName));
  const nav = element("nav");
  const dashboard = element("button", "Dashboard");
  dashboard.type = "button";
  dashboard.onclick = () => navigate("dashboard");
  nav.append(dashboard);
  if (currentUser?.role === "admin") {
    const admin = element("button", "Administration");
    admin.type = "button";
    admin.onclick = () => navigate("admin");
    nav.append(admin);
  }
  const logout = element("button", "Sign out");
  logout.type = "button";
  logout.onclick = async () => {
    try {
      await api<void>("/auth/logout", { method: "POST" });
    } catch (_) {
      // Local credential disposal still protects this browser after a network failure.
    }
    token = null;
    currentUser = null;
    navigate("login");
  };
  nav.append(logout);
  header.append(nav);
  root.append(header, element("h2", title));
}

function renderLogin(error?: string) {
  clear();
  root.append(element("h1", `${appName} sign in`));
  const form = element("form");
  const username = element("input") as HTMLInputElement;
  username.name = "username";
  username.autocomplete = "username";
  username.required = true;
  username.maxLength = 128;
  const password = element("input") as HTMLInputElement;
  password.name = "password";
  password.type = "password";
  password.autocomplete = "current-password";
  password.required = true;
  const submit = element("button", "Sign in") as HTMLButtonElement;
  submit.type = "submit";
  form.append(element("label", "Username"), username, element("label", "Password"), password, submit);
  if (error) root.append(message(error, "error"));
  form.onsubmit = async (event) => {
    event.preventDefault();
    submit.disabled = true;
    try {
      const result = await api<{ access_token: string }>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ username: username.value, password: password.value }),
      });
      token = result.access_token;
      currentUser = await api<User>("/auth/me");
      navigate("dashboard");
    } catch (reason) {
      renderLogin(reason instanceof Error ? reason.message : "Sign in failed.");
    } finally {
      submit.disabled = false;
    }
  };
  root.append(form);
  username.focus();
}

function metric(label: string, value: string | number) {
  const item = element("li");
  item.append(element("strong", String(value)), document.createTextNode(` ${label}`));
  return item;
}

function table(headers: string[], rows: string[][]) {
  const node = element("table");
  const head = element("thead");
  const headRow = element("tr");
  headers.forEach((value) => headRow.append(element("th", value)));
  head.append(headRow);
  const body = element("tbody");
  rows.forEach((values) => {
    const row = element("tr");
    values.forEach((value) => row.append(element("td", value)));
    body.append(row);
  });
  node.append(head, body);
  return node;
}

async function renderDashboard() {
  renderShell("Security dashboard");
  const content = element("section");
  content.append(message("Loading live security data…"));
  root.append(content);
  try {
    const [summary, events, attackers] = await Promise.all([
      api<Summary>("/dashboard/summary"),
      api<{ items: EventItem[] }>("/events?page_size=10"),
      api<{ items: Attacker[] }>("/attackers?page_size=10"),
    ]);
    content.replaceChildren();
    const metrics = element("ul");
    metrics.append(
      metric("events", summary.events),
      metric("attack sources", summary.attackers),
      metric("high-risk events", summary.high_risk),
      metric("active read-only blocks", summary.read_only_block_count),
    );
    content.append(metrics, element("h3", "Recent events"));
    content.append(events.items.length ? table(["Time", "Source IP", "Type", "Severity"], events.items.map((event) => [event.detected_at, event.src_ip, event.attack_type, String(event.severity)])) : message("No recent security events."));
    content.append(element("h3", "Attack sources"));
    content.append(attackers.items.length ? table(["IP", "Events", "Threat score", "Status"], attackers.items.map((attacker) => [attacker.src_ip, String(attacker.total_events), String(attacker.threat_score), attacker.status])) : message("No attack sources found."));
  } catch (reason) {
    content.replaceChildren(message(reason instanceof Error ? reason.message : "Dashboard data is unavailable.", "error"));
    if (!token) {
      const signIn = element("button", "Return to sign in");
      signIn.onclick = () => navigate("login");
      content.append(signIn);
    }
  }
}

async function renderAdmin() {
  if (currentUser?.role !== "admin") {
    renderShell("Access denied");
    root.append(message("You are not allowed to administer user accounts.", "error"));
    return;
  }
  renderShell("User administration");
  const content = element("section");
  content.append(message("Loading users…"));
  root.append(content);
  try {
    const users = await api<User[]>("/admin/users");
    content.replaceChildren();
    if (!users.length) {
      content.append(message("No enabled users found."));
      return;
    }
    const list = element("ul");
    for (const account of users) {
      const row = element("li");
      row.append(element("strong", account.username), document.createTextNode(` — ${account.role}`));
      if (account.id !== currentUser.id) {
        const select = element("select") as HTMLSelectElement;
        (["viewer", "analyst", "admin"] as Role[]).forEach((role) => {
          const option = element("option", role) as HTMLOptionElement;
          option.value = role;
          option.selected = role === account.role;
          select.append(option);
        });
        const save = element("button", "Change role");
        save.type = "button";
        save.onclick = async () => {
          if (!confirm(`Change ${account.username}'s role to ${select.value}?`)) return;
          save.disabled = true;
          try {
            await api<User>(`/admin/users/${account.id}/role`, { method: "PATCH", body: JSON.stringify({ role: select.value }) });
            await renderAdmin();
          } catch (reason) {
            content.prepend(message(reason instanceof Error ? reason.message : "Role change failed.", "error"));
          } finally {
            save.disabled = false;
          }
        };
        row.append(document.createTextNode(" "), select, save);
      }
      list.append(row);
    }
    content.append(list);
  } catch (reason) {
    content.replaceChildren(message(reason instanceof Error ? reason.message : "User list is unavailable.", "error"));
  }
}

function route() {
  const page = location.hash.replace(/^#\//, "") || "dashboard";
  if (!token || !currentUser) {
    renderLogin();
    return;
  }
  if (page === "admin") void renderAdmin();
  else void renderDashboard();
}

window.addEventListener("hashchange", route);
route();
