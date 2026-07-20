/** SecMon P4 operations console. Credentials are intentionally memory-only. */
export const appName = "SecMon";

type Role = "admin" | "analyst" | "viewer";
type User = { id: number; username: string; display_name: string | null; role: Role };
type ApiError = Error & { status?: number; requestId?: string | null };
type EventItem = { id: number; detected_at: string; src_ip: string; attack_type: string; severity: number; username?: string | null; raw_log?: string; handling_status?: string; handling_note?: string | null };
type Attacker = { src_ip: string; total_events: number; threat_score: number; status: string; first_seen?: string; last_seen?: string };
type Alert = { id: number; created_at?: string; updated_at?: string; severity: number; src_ip: string | null; title?: string; description?: string; status: string; assigned_to?: number | null; resolved_at?: string | null };
type Summary = { events: number; attackers: number; high_risk: number; latest_event_at: string | null; read_only_block_count: number; log_source_health: Record<string, number> };

const root = document.getElementById("app") ?? document.body;
let token: string | null = null;
let currentUser: User | null = null;
let sidebarCollapsed = false;

type Route = "login" | "dashboard" | "events" | "event" | "attackers" | "attacker" | "alerts" | "rules" | "operations" | "allowlist" | "audit" | "admin";

function element<K extends keyof HTMLElementTagNameMap>(tag: K, text?: string): HTMLElementTagNameMap[K] {
  const n = document.createElement(tag);
  if (text !== undefined) n.textContent = text;
  return n;
}

function clear() {
  root.replaceChildren();
}

function apiPath(path: string) {
  return `/api/v1${path}`;
}

function text(value: unknown) {
  return value === null || value === undefined || value === "" ? "—" : String(value);
}

function errorText(status: number) {
  return status === 401 ? "Your session has expired. Please sign in again." :
         status === 403 ? "You do not have permission for this operation." :
         status === 404 ? "The requested record was not found." :
         "The request could not be completed.";
}

function svgElement(tag: string, attrs: Record<string, string> = {}): SVGElement {
  const el = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [k, v] of Object.entries(attrs)) {
    el.setAttribute(k, v);
  }
  return el;
}

function createIcon(name: string): SVGElement {
  const base = {
    viewBox: "0 0 24 24",
    width: "18",
    height: "18",
    fill: "none",
    stroke: "currentColor",
    "stroke-width": "2",
    "stroke-linecap": "round",
    "stroke-linejoin": "round"
  };

  if (name === "dashboard") {
    const svg = svgElement("svg", base);
    svg.append(
      svgElement("rect", { x: "3", y: "3", width: "7", height: "9" }),
      svgElement("rect", { x: "14", y: "3", width: "7", height: "5" }),
      svgElement("rect", { x: "14", y: "12", width: "7", height: "9" }),
      svgElement("rect", { x: "3", y: "16", width: "7", height: "5" })
    );
    return svg;
  }
  if (name === "events") {
    const svg = svgElement("svg", base);
    svg.append(svgElement("path", { d: "M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" }));
    return svg;
  }
  if (name === "attackers") {
    const svg = svgElement("svg", base);
    svg.append(
      svgElement("circle", { cx: "12", cy: "12", r: "10" }),
      svgElement("line", { x1: "2", y1: "12", x2: "22", y2: "12" }),
      svgElement("path", { d: "M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" })
    );
    return svg;
  }
  if (name === "alerts") {
    const svg = svgElement("svg", base);
    svg.append(
      svgElement("path", { d: "M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" }),
      svgElement("path", { d: "M13.73 21a2 2 0 0 1-3.46 0" })
    );
    return svg;
  }
  if (name === "rules") {
    const svg = svgElement("svg", base);
    svg.append(
      svgElement("line", { x1: "4", y1: "21", x2: "4", y2: "14" }),
      svgElement("line", { x1: "4", y1: "10", x2: "4", y2: "3" }),
      svgElement("line", { x1: "12", y1: "21", x2: "12", y2: "12" }),
      svgElement("line", { x1: "12", y1: "8", x2: "12", y2: "3" }),
      svgElement("line", { x1: "20", y1: "21", x2: "20", y2: "16" }),
      svgElement("line", { x1: "20", y1: "12", x2: "20", y2: "3" }),
      svgElement("line", { x1: "1", y1: "14", x2: "7", y2: "14" }),
      svgElement("line", { x1: "9", y1: "8", x2: "15", y2: "8" }),
      svgElement("line", { x1: "17", y1: "16", x2: "23", y2: "16" })
    );
    return svg;
  }
  if (name === "operations") {
    const svg = svgElement("svg", base);
    svg.append(
      svgElement("rect", { x: "2", y: "2", width: "20", height: "20", rx: "2.18", ry: "2.18" }),
      svgElement("line", { x1: "6", y1: "2", x2: "6", y2: "22" }),
      svgElement("line", { x1: "18", y1: "2", x2: "18", y2: "22" }),
      svgElement("line", { x1: "2", y1: "12", x2: "22", y2: "12" })
    );
    return svg;
  }
  if (name === "allowlist") {
    const svg = svgElement("svg", base);
    svg.append(
      svgElement("path", { d: "M12 22C17.5228 22 22 17.5228 22 12C22 6.47715 17.5228 2 12 2C6.47715 2 2 6.47715 2 12C2 17.5228 6.47715 22 12 22Z" }),
      svgElement("path", { d: "M9 12L11 14L15 10" })
    );
    return svg;
  }
  if (name === "audit") {
    const svg = svgElement("svg", base);
    svg.append(
      svgElement("path", { d: "M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" }),
      svgElement("polyline", { points: "14 2 14 8 20 8" }),
      svgElement("line", { x1: "16", y1: "13", x2: "8", y2: "13" }),
      svgElement("line", { x1: "16", y1: "17", x2: "8", y2: "17" })
    );
    return svg;
  }
  if (name === "admin") {
    const svg = svgElement("svg", base);
    svg.append(
      svgElement("path", { d: "M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" }),
      svgElement("circle", { cx: "9", cy: "7", r: "4" }),
      svgElement("path", { d: "M23 21v-2a4 4 0 0 0-3-3.87" }),
      svgElement("path", { d: "M16 3.13a4 4 0 0 1 0 7.75" })
    );
    return svg;
  }
  if (name === "logout") {
    const svg = svgElement("svg", base);
    svg.append(
      svgElement("path", { d: "M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" }),
      svgElement("polyline", { points: "16 17 21 12 16 7" }),
      svgElement("line", { x1: "21", y1: "12", x2: "9", y2: "12" })
    );
    return svg;
  }
  if (name === "menu") {
    const svg = svgElement("svg", { ...base, width: "24", height: "24" });
    svg.append(
      svgElement("line", { x1: "3", y1: "12", x2: "21", y2: "12" }),
      svgElement("line", { x1: "3", y1: "6", x2: "21", y2: "6" }),
      svgElement("line", { x1: "3", y1: "18", x2: "21", y2: "18" })
    );
    return svg;
  }

  const svg = svgElement("svg", { ...base, width: "24", height: "24" });
  svg.append(
    svgElement("line", { x1: "18", y1: "6", x2: "6", y2: "18" }),
    svgElement("line", { x1: "6", y1: "6", x2: "18", y2: "18" })
  );
  return svg;
}

function showToast(message: string, type: "success" | "error" | "warning" | "info" = "info") {
  let container = document.getElementById("toast-container");
  if (!container) {
    container = element("div");
    container.id = "toast-container";
    container.className = "toast-container";
    document.body.append(container);
  }
  const toast = element("div");
  toast.className = `toast ${type}`;
  toast.textContent = message;
  container.append(toast);
  setTimeout(() => {
    toast.remove();
  }, 4000);
}

function showModal(title: string, message: string, isPrompt: boolean, defaultValue = ""): Promise<string | null> {
  return new Promise(resolve => {
    const overlay = element("div");
    overlay.className = "modal-overlay";

    const container = element("div");
    container.className = "modal-container";

    const t = element("div", title);
    t.className = "modal-title";

    const msg = element("div", message);
    msg.className = "modal-message";

    container.append(t, msg);

    let input: HTMLInputElement | null = null;
    if (isPrompt) {
      input = element("input") as HTMLInputElement;
      input.className = "modal-input";
      input.value = defaultValue;
      container.append(input);
    }

    const actions = element("div");
    actions.className = "modal-actions";

    const cancelBtn = element("button", "Cancel");
    cancelBtn.className = "btn btn-secondary";
    cancelBtn.onclick = () => {
      overlay.remove();
      resolve(null);
    };

    const okBtn = element("button", "Confirm");
    okBtn.className = "btn btn-primary";
    okBtn.onclick = () => {
      const val = input ? input.value : "confirmed";
      overlay.remove();
      resolve(val);
    };

    actions.append(cancelBtn, okBtn);
    container.append(actions);
    overlay.append(container);
    document.body.append(overlay);

    if (input) {
      input.focus();
      input.onkeydown = e => {
        if (e.key === "Enter") okBtn.click();
        if (e.key === "Escape") cancelBtn.click();
      };
    } else {
      okBtn.focus();
    }

    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        document.removeEventListener("keydown", handleEsc);
        cancelBtn.click();
      }
    };
    document.addEventListener("keydown", handleEsc);
  });
}

async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body) headers.set("Content-Type", "application/json");

  const response = await fetch(apiPath(path), { ...init, headers });
  const requestId = response.headers.get("X-Request-ID");

  if (!response.ok) {
    const e = new Error(errorText(response.status)) as ApiError;
    e.status = response.status;
    e.requestId = requestId;
    if (response.status === 401) {
      token = null;
      currentUser = null;
    }
    throw e;
  }
  return response.status === 204 ? undefined as T : response.json() as Promise<T>;
}

function navigate(page: Route, id?: string | number) {
  location.hash = `#/${page}${id === undefined ? "" : `/${encodeURIComponent(String(id))}`}`;
}

function notice(value: string, kind: "error" | "notice" = "notice") {
  const n = element("p", value);
  n.className = `alert ${kind === "error" ? "error" : "info"}`;
  n.setAttribute("role", kind === "error" ? "alert" : "status");
  return n;
}

function renderSkeleton(container: HTMLElement, rowCount = 5) {
  container.replaceChildren();
  const skeleton = element("div");
  skeleton.className = "skeleton-container";
  for (let i = 0; i < rowCount; i++) {
    const row = element("div");
    row.className = "skeleton-row" + (i % 2 === 0 ? " medium" : i % 3 === 0 ? " short" : "");
    skeleton.append(row);
  }
  container.append(skeleton);
}

function loading(container: HTMLElement, label = "Loading security data…") {
  renderSkeleton(container);
}

function can(minimum: Role) {
  return !!currentUser && ["viewer", "analyst", "admin"].indexOf(currentUser.role) >= ["viewer", "analyst", "admin"].indexOf(minimum);
}

function guarded(minimum: Role, title: string) {
  if (can(minimum)) return true;
  renderShell(title);
  root.append(notice("You are not allowed to access this page.", "error"));
  return false;
}

function displayError(container: HTMLElement, reason: unknown, retryAction?: () => void) {
  container.replaceChildren();
  const errCard = element("div");
  errCard.className = "error-state";

  const icon = element("div", "⚠️");
  icon.className = "state-icon";

  const title = element("div", "Service Interruption");
  title.className = "state-title";

  const message = reason instanceof Error ? reason.message : "Security data is temporarily unavailable.";
  const desc = element("div", message);
  desc.className = "state-desc";
  errCard.append(icon, title, desc);

  const status = (reason as any).status;
  const requestId = (reason as any).requestId;
  if (requestId) {
    const debugId = element("div", `Request ID: ${requestId}`);
    debugId.className = "error-details";
    errCard.append(debugId);
  } else if (status) {
    const debugId = element("div", `Status Code: ${status}`);
    debugId.className = "error-details";
    errCard.append(debugId);
  }

  if (retryAction) {
    const retryBtn = button("Retry Connection", retryAction);
    retryBtn.className = "btn btn-primary";
    errCard.append(retryBtn);
  }
  container.append(errCard);
}

function renderShell(title: string, subtitle = "Enterprise Linux Security Console"): HTMLElement {
  clear();

  const container = element("div");
  container.className = "app-container";

  const sidebar = element("div");
  sidebar.className = "sidebar" + (sidebarCollapsed ? " collapsed" : "");

  const sbHeader = element("div");
  sbHeader.className = "sidebar-header";

  const sbBrand = element("div");
  sbBrand.className = "sidebar-brand";
  const brandText = element("span", appName);
  brandText.className = "sidebar-brand-text";
  sbBrand.append(createIcon("dashboard"), brandText);

  const sbToggle = element("button");
  sbToggle.className = "sidebar-toggle-btn";
  sbToggle.append(sidebarCollapsed ? createIcon("menu") : createIcon("close"));
  sbToggle.onclick = () => {
    sidebarCollapsed = !sidebarCollapsed;
    sidebar.classList.toggle("collapsed", sidebarCollapsed);
    sbToggle.replaceChildren(sidebarCollapsed ? createIcon("menu") : createIcon("close"));
  };

  sbHeader.append(sbBrand, sbToggle);
  sidebar.append(sbHeader);

  const nav = element("nav");
  nav.className = "sidebar-nav";

  const links: Array<[string, Route, Role, string]> = [
    ["Dashboard", "dashboard", "viewer", "dashboard"],
    ["Events", "events", "viewer", "events"],
    ["Attack IPs", "attackers", "viewer", "attackers"],
    ["Alerts", "alerts", "viewer", "alerts"],
    ["Alert rules", "rules", "admin", "rules"],
    ["Operations", "operations", "viewer", "operations"],
    ["Allowlist", "allowlist", "admin", "allowlist"],
    ["Audit log", "audit", "admin", "audit"],
    ["Users", "admin", "admin", "admin"]
  ];

  const [currentPage = "dashboard"] = location.hash.replace(/^#\//, "").split("/");

  links.forEach(([label, page, role, iconName]) => {
    if (can(role)) {
      const item = element("button");
      item.className = "nav-item" + (currentPage === page ? " active" : "");
      item.onclick = () => {
        sidebar.classList.remove("mobile-open");
        backdrop.classList.remove("show");
        navigate(page);
      };

      const iconSpan = element("span");
      iconSpan.className = "nav-icon";
      iconSpan.append(createIcon(iconName));

      const labelSpan = element("span", label);
      labelSpan.className = "nav-label";

      item.append(iconSpan, labelSpan);
      nav.append(item);
    }
  });

  sidebar.append(nav);

  const sbFooter = element("div");
  sbFooter.className = "sidebar-footer";

  if (currentUser) {
    const userSummary = element("div");
    userSummary.className = "user-profile-summary";

    const avatar = element("div", currentUser.username.substring(0, 2).toUpperCase());
    avatar.className = "user-avatar";

    const info = element("div");
    info.className = "user-info";
    const nameSpan = element("span", currentUser.display_name || currentUser.username);
    nameSpan.className = "user-name";
    const roleSpan = element("span", currentUser.role.toUpperCase());
    roleSpan.className = "user-role";
    info.append(nameSpan, roleSpan);

    userSummary.append(avatar, info);
    sbFooter.append(userSummary);
  }

  const logout = element("button");
  logout.className = "logout-btn";
  const logoutIcon = element("span");
  logoutIcon.className = "nav-icon";
  logoutIcon.append(createIcon("logout"));
  const logoutLabel = element("span", "Sign out");
  logoutLabel.className = "nav-label";
  logout.append(logoutIcon, logoutLabel);
  logout.onclick = async () => {
    try {
      await api<void>("/auth/logout", { method: "POST" });
    } catch {
      // Ignored
    }
    token = null;
    currentUser = null;
    navigate("login");
  };

  sbFooter.append(logout);
  sidebar.append(sbFooter);

  const backdrop = element("div");
  backdrop.className = "mobile-nav-backdrop";
  backdrop.onclick = () => {
    sidebar.classList.remove("mobile-open");
    backdrop.classList.remove("show");
  };

  const mainContent = element("div");
  mainContent.className = "main-content";

  const header = element("header");
  header.className = "main-header";

  const headerLeft = element("div");
  headerLeft.className = "header-left";

  const mobMenuBtn = element("button");
  mobMenuBtn.className = "header-mobile-menu-btn";
  mobMenuBtn.append(createIcon("menu"));
  mobMenuBtn.onclick = () => {
    sidebar.classList.add("mobile-open");
    backdrop.classList.add("show");
  };

  const titleContainer = element("div");
  titleContainer.className = "header-title-container";
  const headerTitle = element("h2", title);
  const headerSub = element("span", subtitle);
  headerSub.className = "header-subtitle";
  titleContainer.append(headerTitle, headerSub);

  headerLeft.append(mobMenuBtn, titleContainer);
  header.append(headerLeft);

  const headerRight = element("div");
  headerRight.className = "header-right";
  if (currentUser) {
    const headerUserBadge = element("span", `${currentUser.username} (${currentUser.role})`);
    headerUserBadge.className = "badge neutral";
    headerRight.append(headerUserBadge);
  }
  header.append(headerRight);

  const viewBody = element("div");
  viewBody.className = "view-body";

  mainContent.append(header, viewBody);

  const mobBottomNav = element("div");
  mobBottomNav.className = "mobile-bottom-nav";

  const quickLinks: Array<[string, Route, string]> = [
    ["Dash", "dashboard", "dashboard"],
    ["Events", "events", "events"],
    ["IPs", "attackers", "attackers"],
    ["Alerts", "alerts", "alerts"]
  ];

  quickLinks.forEach(([label, page, iconName]) => {
    const btn = element("button");
    btn.className = "mobile-bottom-nav-item" + (currentPage === page ? " active" : "");
    btn.onclick = () => navigate(page);

    const iconSpan = element("span");
    iconSpan.className = "mobile-bottom-nav-icon";
    iconSpan.append(createIcon(iconName));

    const labelSpan = element("span", label);
    btn.append(iconSpan, labelSpan);
    mobBottomNav.append(btn);
  });

  container.append(sidebar, backdrop, mainContent, mobBottomNav);
  root.append(container);

  const handleKeydown = (e: KeyboardEvent) => {
    if (e.key === "Escape") {
      sidebar.classList.remove("mobile-open");
      backdrop.classList.remove("show");
    }
  };
  document.addEventListener("keydown", handleKeydown);

  return viewBody;
}

function table(headers: string[], rows: Array<Array<string | Node>>): HTMLElement {
  const container = element("div");
  container.className = "table-container";

  const t = element("table");
  const head = element("thead");
  const hr = element("tr");
  headers.forEach(x => hr.append(element("th", x)));
  head.append(hr);

  const body = element("tbody");
  rows.forEach(values => {
    const tr = element("tr");
    values.forEach(value => {
      const td = element("td");
      if (typeof value === "string") {
        td.textContent = value;
      } else {
        td.append(value);
      }
      tr.append(td);
    });
    body.append(tr);
  });

  t.append(head, body);
  container.append(t);
  return container;
}

function button(label: string, action: () => void | Promise<void>) {
  const b = element("button", label);
  b.type = "button";
  b.className = "btn btn-primary";
  b.onclick = () => void action();
  return b;
}

async function requiredReason(label: string, action: (reason: string) => Promise<void>) {
  const reason = await showModal(label, "Provide the operational reason (required):", true);
  if (!reason || !reason.trim()) {
    showToast("Action cancelled: reason is required", "warning");
    return;
  }
  const confirmed = await showModal(label, `Are you sure you want to perform: ${label}? This will be audited.`, false);
  if (!confirmed) {
    showToast("Action cancelled", "info");
    return;
  }
  try {
    await action(reason.trim());
    showToast("Operation completed successfully", "success");
  } catch (err: any) {
    showToast(err.message || "Operation failed", "error");
    throw err;
  }
}

function severity(value: number) {
  return `S${value}`;
}

function severityBadge(val: number): HTMLElement {
  const span = element("span", `S${val}`);
  span.className = `badge s${Math.min(5, Math.max(1, val))}`;
  return span;
}

function resultBadge(res: string): HTMLElement {
  const span = element("span", res);
  const low = res.toLowerCase();
  if (low === "success" || low === "ok" || low === "active" || low === "available" || low === "present" || low === "true") {
    span.className = "badge success";
  } else if (low === "failed" || low === "error" || low === "denied" || low === "unavailable" || low === "missing" || low === "inactive" || low === "false") {
    span.className = "badge danger";
  } else if (low === "warning" || low === "degraded") {
    span.className = "badge warning";
  } else {
    span.className = "badge neutral";
  }
  return span;
}

function mobileRow(label: string, value: string | Node): HTMLElement {
  const row = element("div");
  row.className = "mobile-data-card-row";
  const lbl = element("span", label);
  lbl.className = "mobile-data-card-label";
  const val = element("span");
  val.className = "mobile-data-card-value";
  if (typeof value === "string") {
    val.textContent = value;
  } else {
    val.append(value);
  }
  row.append(lbl, val);
  return row;
}

function requestIdElement(id: string): HTMLElement {
  const container = element("span");
  if (id === "—" || !id.trim()) {
    container.textContent = "—";
    return container;
  }

  const code = element("code", id);
  code.style.fontFamily = "monospace";
  code.style.background = "rgba(0,0,0,0.3)";
  code.style.padding = "2px 6px";
  code.style.borderRadius = "4px";
  code.style.fontSize = "12px";

  const copyBtn = element("button", "Copy");
  copyBtn.className = "copy-btn";
  copyBtn.onclick = () => {
    navigator.clipboard.writeText(id).then(() => {
      copyBtn.textContent = "Copied!";
      copyBtn.style.color = "var(--success)";
      showToast("Request ID copied", "success");
      setTimeout(() => {
        copyBtn.textContent = "Copy";
        copyBtn.style.color = "";
      }, 1500);
    }).catch(() => {
      showToast("Copy failed", "error");
    });
  };

  container.append(code, copyBtn);
  return container;
}

// ---------------------- PAGE RENDERERS ----------------------

function renderLogin(error?: string) {
  clear();

  const view = element("div");
  view.className = "login-view";

  const card = element("div");
  card.className = "login-card";

  const brand = element("div", appName);
  brand.className = "login-brand";

  const tagline = element("div", "Enterprise Security Monitoring & Firewall Management");
  tagline.className = "login-tagline";

  card.append(brand, tagline);

  if (error) {
    const banner = element("div", error);
    banner.className = "alert error";
    card.append(banner);
  }

  const form = element("form");

  const userGroup = element("div");
  userGroup.className = "form-group";
  const userLabel = element("label", "Username");
  const userInput = element("input") as HTMLInputElement;
  userInput.className = "form-control";
  userInput.required = true;
  userInput.autocomplete = "username";
  userInput.maxLength = 128;
  userGroup.append(userLabel, userInput);

  const passGroup = element("div");
  passGroup.className = "form-group";
  const passLabel = element("label", "Password");
  const passWrapper = element("div");
  passWrapper.className = "input-wrapper";

  const passInput = element("input") as HTMLInputElement;
  passInput.className = "form-control";
  passInput.required = true;
  passInput.type = "password";
  passInput.autocomplete = "current-password";

  const toggleBtn = element("button", "Show") as HTMLButtonElement;
  toggleBtn.type = "button";
  toggleBtn.className = "password-toggle";
  toggleBtn.onclick = () => {
    if (passInput.type === "password") {
      passInput.type = "text";
      toggleBtn.textContent = "Hide";
    } else {
      passInput.type = "password";
      toggleBtn.textContent = "Show";
    }
  };

  passWrapper.append(passInput, toggleBtn);
  passGroup.append(passLabel, passWrapper);

  const submit = element("button", "Sign in") as HTMLButtonElement;
  submit.type = "submit";
  submit.className = "submit-btn";

  form.append(userGroup, passGroup, submit);

  form.onsubmit = async e => {
    e.preventDefault();
    submit.disabled = true;
    submit.textContent = "Authenticating...";
    try {
      const res = await api<{ access_token: string }>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ username: userInput.value, password: passInput.value })
      });
      token = res.access_token;
      currentUser = await api<User>("/auth/me");
      showToast(`Welcome back, ${currentUser.username}!`, "success");
      navigate("dashboard");
    } catch (r) {
      renderLogin(r instanceof Error ? r.message : "Sign in failed.");
    } finally {
      submit.disabled = false;
      submit.textContent = "Sign in";
    }
  };

  card.append(form);
  view.append(card);
  root.append(view);

  userInput.focus();
}

async function renderDashboard() {
  if (!guarded("viewer", "Security Dashboard")) return;
  const view = renderShell("Security Dashboard", "Real-time threat landscape and mitigation metrics");

  const content = element("div");
  view.append(content);

  renderSkeleton(content);

  try {
    const [summary, events, attackers, health] = await Promise.all([
      api<Summary>("/dashboard/summary"),
      api<{items: EventItem[]}>("/events?page_size=10"),
      api<{items: Attacker[]}>("/attackers?page_size=10"),
      api<{status: string}>("/operations/health").catch(() => ({ status: "unavailable" }))
    ]);

    content.replaceChildren();

    const statsGrid = element("div");
    statsGrid.className = "stats-grid";

    const itemsList: Array<[string, number | string, string, string]> = [
      ["Events", summary.events, "var(--primary)", "Recorded events"],
      ["Attack sources", summary.attackers, "var(--secondary)", "Distinct attackers"],
      ["High-risk events", summary.high_risk, "var(--danger)", "Severity S4+ events"],
      ["Active blocks", summary.read_only_block_count, "var(--warning)", "Firewall blocks"],
      ["Operations", health.status, "var(--success)", "Service status"]
    ];

    itemsList.forEach(([label, value, color, desc]) => {
      const card = element("div");
      card.className = "stat-card";
      card.style.setProperty("--accent-color", color);

      const title = element("div", label);
      title.className = "stat-title";

      const val = element("div");
      val.className = "stat-value";
      if (typeof value === "string") {
        val.append(resultBadge(value));
      } else {
        val.textContent = text(value);
      }

      const footer = element("div", desc);
      footer.className = "stat-footer";

      card.append(title, val, footer);
      statsGrid.append(card);
    });

    content.append(statsGrid);

    const eventsCard = element("div");
    eventsCard.className = "card";
    const eventsTitle = element("div", "Recent Events");
    eventsTitle.className = "card-title";
    eventsCard.append(eventsTitle);

    if (events.items.length) {
      const dt = table(["Time", "Source IP", "Type", "Severity", ""], events.items.map(x => [
        text(x.detected_at),
        x.src_ip,
        x.attack_type,
        severityBadge(x.severity),
        button("View", () => navigate("event", x.id))
      ]));

      const mobList = element("div");
      mobList.className = "responsive-card-list mobile-only";
      events.items.forEach(x => {
        const c = element("div");
        c.className = "mobile-data-card";
        c.append(
          mobileRow("Time", text(x.detected_at)),
          mobileRow("Source IP", x.src_ip),
          mobileRow("Type", x.attack_type),
          mobileRow("Severity", severityBadge(x.severity)),
          mobileRow("Actions", button("View", () => navigate("event", x.id)))
        );
        mobList.append(c);
      });

      eventsCard.append(dt, mobList);
    } else {
      const empty = element("div");
      empty.className = "empty-state";
      empty.append(element("div", "No recent security events."));
      eventsCard.append(empty);
    }

    content.append(eventsCard);

    const attackersCard = element("div");
    attackersCard.className = "card";
    const attackersTitle = element("div", "Top Attack Sources");
    attackersTitle.className = "card-title";
    attackersCard.append(attackersTitle);

    if (attackers.items.length) {
      const dt = table(["IP", "Events", "Threat Score", "Status", ""], attackers.items.map(x => [
        x.src_ip,
        text(x.total_events),
        text(x.threat_score),
        resultBadge(x.status),
        button("Details", () => navigate("attacker", x.src_ip))
      ]));

      const mobList = element("div");
      mobList.className = "responsive-card-list mobile-only";
      attackers.items.forEach(x => {
        const c = element("div");
        c.className = "mobile-data-card";
        c.append(
          mobileRow("IP", x.src_ip),
          mobileRow("Events", text(x.total_events)),
          mobileRow("Threat Score", text(x.threat_score)),
          mobileRow("Status", resultBadge(x.status)),
          mobileRow("Actions", button("Details", () => navigate("attacker", x.src_ip)))
        );
        mobList.append(c);
      });

      attackersCard.append(dt, mobList);
    } else {
      const empty = element("div");
      empty.className = "empty-state";
      empty.append(element("div", "No attack sources detected."));
      attackersCard.append(empty);
    }

    content.append(attackersCard);

  } catch (r) {
    displayError(content, r, () => void renderDashboard());
  }
}

function filterInput(placeholder: string) {
  const input = element("input") as HTMLInputElement;
  input.placeholder = placeholder;
  input.maxLength = 128;
  return input;
}

async function renderEvents() {
  if (!guarded("viewer", "Event Center")) return;
  const view = renderShell("Event Center", "Query and analyze normalized security events");

  const content = element("div");
  view.append(content);

  const filters = element("form");
  filters.className = "filters-bar";

  const ip = filterInput("Source IP");
  const type = filterInput("Attack Type");
  const sev = element("select") as HTMLSelectElement;

  const anyOpt = element("option", "Any Severity");
  anyOpt.value = "";
  sev.append(anyOpt);

  for (let i = 1; i <= 5; i++) {
    const o = element("option", `Severity ${i}`) as HTMLOptionElement;
    o.value = String(i);
    sev.append(o);
  }

  const applyBtn = button("Apply Filters", () => void load());
  filters.append(ip, type, sev, applyBtn);
  filters.onsubmit = e => {
    e.preventDefault();
    void load();
  };

  content.append(filters);

  const resultsContainer = element("div");
  content.append(resultsContainer);

  async function load() {
    renderSkeleton(resultsContainer);
    try {
      const q = new URLSearchParams({ page_size: "50" });
      if (ip.value.trim()) q.set("source_ip", ip.value.trim());
      if (type.value.trim()) q.set("attack_type", type.value.trim());
      if (sev.value) q.set("severity", sev.value);

      const result = await api<{ items: EventItem[]; total: number }>(`/events?${q}`);

      resultsContainer.replaceChildren();

      const stats = element("p", `${result.total} matching events`);
      stats.style.marginBottom = "15px";
      stats.style.color = "var(--text-muted)";
      resultsContainer.append(stats);

      if (result.items.length) {
        const dt = table(["Time", "Source", "Type", "Severity", "User", ""], result.items.map(x => [
          text(x.detected_at),
          x.src_ip,
          x.attack_type,
          severityBadge(x.severity),
          text(x.username),
          button("Details", () => navigate("event", x.id))
        ]));

        const mobList = element("div");
        mobList.className = "responsive-card-list mobile-only";
        result.items.forEach(x => {
          const c = element("div");
          c.className = "mobile-data-card";
          c.append(
            mobileRow("Time", text(x.detected_at)),
            mobileRow("Source IP", x.src_ip),
            mobileRow("Type", x.attack_type),
            mobileRow("Severity", severityBadge(x.severity)),
            mobileRow("User", text(x.username)),
            mobileRow("Actions", button("Details", () => navigate("event", x.id)))
          );
          mobList.append(c);
        });

        resultsContainer.append(dt, mobList);
      } else {
        const empty = element("div");
        empty.className = "empty-state";
        empty.append(element("div", "No events match these filters."));
        resultsContainer.append(empty);
      }
    } catch (r) {
      displayError(resultsContainer, r, () => void load());
    }
  }

  await load();
}

async function renderEvent(id: string) {
  if (!guarded("viewer", "Event Detail")) return;
  const view = renderShell("Event Detail", `Detailed diagnostics for Event #${id}`);

  const content = element("div");
  view.append(content);

  renderSkeleton(content);

  try {
    const event = await api<EventItem>(`/events/${encodeURIComponent(id)}`);
    content.replaceChildren();

    const card = element("div");
    card.className = "card";

    const values: Array<[string, unknown]> = [
      ["Detected Time", event.detected_at],
      ["Source IP", event.src_ip],
      ["Attack Type", event.attack_type],
      ["Severity Level", severity(event.severity)],
      ["Target Username", event.username],
      ["Handling Status", event.handling_status],
      ["Handling Note", event.handling_note]
    ];

    const list = element("dl");
    values.forEach(([l, v]) => {
      const labelElement = element("dt", l);
      const valElement = element("dd");
      if (l === "Severity Level" && typeof v === "string") {
        const sevVal = parseInt(v.replace("S", ""));
        valElement.append(severityBadge(isNaN(sevVal) ? event.severity : sevVal));
      } else if (l === "Handling Status" && typeof v === "string") {
        valElement.append(resultBadge(v));
      } else {
        valElement.textContent = text(v);
      }
      list.append(labelElement, valElement);
    });

    card.append(list);

    const actions = element("div");
    actions.style.display = "flex";
    actions.style.gap = "12px";
    actions.style.marginBottom = "24px";

    if (can("analyst")) {
      const updateBtn = button("Update Handling Status", async () => {
        const status = await showModal(
          "Update Disposition",
          "Select status: new, investigating, resolved, false_positive, ignored",
          true,
          event.handling_status ?? "new"
        );
        if (!status || !["new", "investigating", "resolved", "false_positive", "ignored"].includes(status)) {
          showToast("Invalid handling status selected", "warning");
          return;
        }

        const note = await showModal("Add Handling Note", "Provide the operational context (required):", true, event.handling_note ?? "");
        if (!note || !note.trim()) {
          showToast("Handling note is required", "warning");
          return;
        }

        await api(`/events/${encodeURIComponent(id)}/disposition`, {
          method: "PATCH",
          body: JSON.stringify({ status, handling_note: note.trim() })
        });
        showToast("Event disposition updated", "success");
        await renderEvent(id);
      });
      actions.append(updateBtn);
    }

    const backBtn = button("Back to Events", () => navigate("events"));
    backBtn.className = "btn btn-secondary";
    actions.append(backBtn);
    card.append(actions);

    if (event.raw_log) {
      const details = element("details");
      const summary = element("summary", "Raw Log Payload (Untrusted String)");
      const pre = element("pre", event.raw_log);
      details.append(summary, pre);
      card.append(details);
    }

    content.append(card);
  } catch (r) {
    displayError(content, r, () => void renderEvent(id));
  }
}

async function renderAttackers() {
  if (!guarded("viewer", "Attack IPs")) return;
  const view = renderShell("Attack IPs", "Database of attackers and observed source hosts");

  const content = element("div");
  view.append(content);

  renderSkeleton(content);

  try {
    const result = await api<{ items: Attacker[]; total: number }>("/attackers?page_size=50");
    content.replaceChildren();

    const stats = element("p", `${result.total} observed attacker sources`);
    stats.style.marginBottom = "15px";
    stats.style.color = "var(--text-muted)";
    content.append(stats);

    if (result.items.length) {
      const dt = table(["IP Address", "Total Events", "Threat Score", "Status", "Last Seen", ""], result.items.map(x => [
        x.src_ip,
        text(x.total_events),
        text(x.threat_score),
        resultBadge(x.status),
        text(x.last_seen),
        button("Details", () => navigate("attacker", x.src_ip))
      ]));

      const mobList = element("div");
      mobList.className = "responsive-card-list mobile-only";
      result.items.forEach(x => {
        const c = element("div");
        c.className = "mobile-data-card";
        c.append(
          mobileRow("IP Address", x.src_ip),
          mobileRow("Events", text(x.total_events)),
          mobileRow("Threat Score", text(x.threat_score)),
          mobileRow("Status", resultBadge(x.status)),
          mobileRow("Last Seen", text(x.last_seen)),
          mobileRow("Actions", button("Details", () => navigate("attacker", x.src_ip)))
        );
        mobList.append(c);
      });

      content.append(dt, mobList);
    } else {
      const empty = element("div");
      empty.className = "empty-state";
      empty.append(element("div", "No attacker IP records found."));
      content.append(empty);
    }
  } catch (r) {
    displayError(content, r, () => void renderAttackers());
  }
}

async function renderAttacker(ip: string) {
  if (!guarded("viewer", "Attack IP Detail")) return;
  const view = renderShell("Attack IP Detail", `Profile dashboard for source IP: ${ip}`);

  const content = element("div");
  view.append(content);

  renderSkeleton(content);

  try {
    const result = await api<{ summary: Attacker; recent_events: EventItem[]; read_only_blocked: boolean }>(`/attackers/${encodeURIComponent(ip)}`);
    content.replaceChildren();

    const s = result.summary;

    const summaryCard = element("div");
    summaryCard.className = "card";

    const summaryText = element("h3", `${s.src_ip} [Status: ${s.status}]`);
    summaryText.style.marginBottom = "12px";

    const metaList = element("dl");
    metaList.append(
      element("dt", "Threat Score"), element("dd", text(s.threat_score)),
      element("dt", "Total Events Count"), element("dd", text(s.total_events)),
      element("dt", "First Seen"), element("dd", text(s.first_seen)),
      element("dt", "Last Seen"), element("dd", text(s.last_seen))
    );

    summaryCard.append(summaryText, metaList);

    const blockAlert = notice(result.read_only_blocked ? "This IP is currently blocked on the firewall." : "This IP is not currently blocked.", result.read_only_blocked ? "error" : "notice");
    summaryCard.append(blockAlert);

    if (can("admin")) {
      const controls = element("p");
      controls.style.display = "flex";
      controls.style.gap = "12px";
      controls.style.marginTop = "20px";

      const blockBtn = button("Block IP", async () => {
        await requiredReason(`Block IP ${s.src_ip}`, async reason => {
          await api("/firewall/blocks", {
            method: "POST",
            body: JSON.stringify({ ip: s.src_ip, reason })
          });
          await renderAttacker(ip);
        });
      });
      blockBtn.className = "btn btn-danger";

      const allowBtn = button("Add to Allowlist", async () => {
        await requiredReason(`Add ${s.src_ip} to Allowlist`, async reason => {
          await api("/allowlist", {
            method: "POST",
            body: JSON.stringify({ ip_or_cidr: s.src_ip, description: reason })
          });
          await renderAttacker(ip);
        });
      });
      allowBtn.className = "btn btn-primary";

      controls.append(blockBtn, allowBtn);
      summaryCard.append(controls);
    }

    content.append(summaryCard);

    const eventsCard = element("div");
    eventsCard.className = "card";
    const eventsTitle = element("h3", "Recent Events from Source");
    eventsTitle.style.marginBottom = "15px";
    eventsCard.append(eventsTitle);

    if (result.recent_events.length) {
      const dt = table(["Time", "Attack Type", "Severity", ""], result.recent_events.map(x => [
        text(x.detected_at),
        x.attack_type,
        severityBadge(x.severity),
        button("View", () => navigate("event", x.id))
      ]));

      const mobList = element("div");
      mobList.className = "responsive-card-list mobile-only";
      result.recent_events.forEach(x => {
        const c = element("div");
        c.className = "mobile-data-card";
        c.append(
          mobileRow("Time", text(x.detected_at)),
          mobileRow("Type", x.attack_type),
          mobileRow("Severity", severityBadge(x.severity)),
          mobileRow("Actions", button("View", () => navigate("event", x.id)))
        );
        mobList.append(c);
      });
      eventsCard.append(dt, mobList);
    } else {
      const empty = element("div");
      empty.className = "empty-state";
      empty.append(element("div", "No events registered."));
      eventsCard.append(empty);
    }

    eventsCard.style.marginTop = "24px";
    content.append(eventsCard);
  } catch (r) {
    displayError(content, r, () => void renderAttacker(ip));
  }
}

async function renderAlerts() {
  if (!guarded("viewer", "Alert settings and triage")) return;
  const view = renderShell("Alert Triage Hub", "Manage escalated security notifications and analyst triage decisions");

  const content = element("div");
  view.append(content);

  renderSkeleton(content);

  try {
    const result = await api<{ items: Alert[]; total?: number }>("/alerts?page_size=50");
    content.replaceChildren();

    const countText = element("p", `${text(result.total ?? result.items.length)} active alerts require review`);
    countText.style.marginBottom = "15px";
    countText.style.color = "var(--text-muted)";
    content.append(countText);

    if (result.items.length) {
      const rows = result.items.map(a => {
        const actions = element("span");
        if (can("analyst") && !["resolved", "ignored"].includes(a.status)) {
          const ack = button("Acknowledge", () => void updateAlert(a, "acknowledged"));
          ack.className = "btn btn-secondary btn-sm";

          const inv = button("Investigate", () => void updateAlert(a, "investigating"));
          inv.className = "btn btn-primary btn-sm";
          inv.style.margin = "0 6px";

          const res = button("Resolve", () => void updateAlert(a, "resolved"));
          res.className = "btn btn-secondary btn-sm";

          actions.append(ack, inv, res);
        } else {
          actions.textContent = "No triage actions required";
        }

        return [
          text(a.created_at),
          severityBadge(a.severity),
          text(a.src_ip),
          text(a.title),
          resultBadge(a.status),
          actions
        ] as Array<string | Node>;
      });

      const dt = table(["Created", "Severity", "Source IP", "Alert Description", "Status", "Actions"], rows);

      const mobList = element("div");
      mobList.className = "responsive-card-list mobile-only";
      result.items.forEach(a => {
        const actions = element("div");
        if (can("analyst") && !["resolved", "ignored"].includes(a.status)) {
          const ack = button("Ack", () => void updateAlert(a, "acknowledged"));
          ack.className = "btn btn-secondary btn-sm";
          const inv = button("Investigate", () => void updateAlert(a, "investigating"));
          inv.className = "btn btn-primary btn-sm";
          inv.style.margin = "0 6px";
          const res = button("Resolve", () => void updateAlert(a, "resolved"));
          res.className = "btn btn-secondary btn-sm";
          actions.append(ack, inv, res);
        } else {
          actions.textContent = "—";
        }

        const c = element("div");
        c.className = "mobile-data-card";
        c.append(
          mobileRow("Created", text(a.created_at)),
          mobileRow("Severity", severityBadge(a.severity)),
          mobileRow("Source IP", text(a.src_ip)),
          mobileRow("Alert", text(a.title)),
          mobileRow("Status", resultBadge(a.status)),
          mobileRow("Actions", actions)
        );
        mobList.append(c);
      });

      content.append(dt, mobList);
    } else {
      const empty = element("div");
      empty.className = "empty-state";
      empty.append(element("div", "No escalated alerts requiring triage."));
      content.append(empty);
    }

    async function updateAlert(alert: Alert, status: string) {
      await requiredReason(`Set alert #${alert.id} status to: ${status}`, async reason => {
        await api(`/alerts/${alert.id}`, {
          method: "PATCH",
          body: JSON.stringify({ status, reason })
        });
        await renderAlerts();
      });
    }
  } catch (r) {
    displayError(content, r, () => void renderAlerts());
  }
}

async function renderRules() {
  if (!guarded("admin", "Alert Rules")) return;
  const view = renderShell("Alert Rules & Escalation", "Configure threat threshold triggers and notification channels");

  const content = element("div");
  view.append(content);

  renderSkeleton(content);

  try {
    const [rules, deliveries] = await Promise.all([
      api<{ items: Array<Record<string, any>> }>("/alert-rules"),
      api<{ items: Array<Record<string, any>> }>("/alert-deliveries")
    ]);

    content.replaceChildren();

    const card = element("div");
    card.className = "card";

    const createBtn = button("Create Simulation Rule", async () => {
      const name = await showModal("Create Rule", "Enter simulation rule name:", true);
      if (!name || !name.trim()) {
        showToast("Rule name is required", "warning");
        return;
      }
      try {
        await api("/alert-rules", {
          method: "POST",
          body: JSON.stringify({
            name: name.trim(),
            minimum_severity: 4,
            event_threshold: 1,
            window_minutes: 5,
            suppression_minutes: 15,
            channels: ["simulation"],
            recipients: []
          })
        });
        showToast("Simulation rule created", "success");
        await renderRules();
      } catch (err: any) {
        showToast(err.message || "Failed to create rule", "error");
      }
    });
    createBtn.style.marginBottom = "20px";
    card.append(createBtn);

    if (rules.items.length) {
      const dt = table(["Rule Name", "Enabled", "Min Severity", "Threshold / Window", "Channels", "Actions"], rules.items.map(r => {
        const testBtn = button("Test Sim", async () => {
          try {
            const res = await api<{ status: string }>(`/alert-rules/${r.id}/test`, {
              method: "POST",
              body: JSON.stringify({ channel: "simulation" })
            });
            showToast(`Test triggered. Delivery status: ${res.status}`, "success");
            await renderRules();
          } catch (err: any) {
            showToast(err.message || "Test failed", "error");
          }
        });
        testBtn.className = "btn btn-secondary btn-sm";

        return [
          text(r.name),
          resultBadge(r.enabled ? "Active" : "Disabled"),
          severityBadge(Number(r.minimum_severity)),
          `${r.event_threshold} events / ${r.window_minutes} min`,
          text(JSON.stringify(r.channels)),
          testBtn
        ];
      }));
      card.append(dt);
    } else {
      const empty = element("div");
      empty.className = "empty-state";
      empty.append(element("div", "No rules configured."));
      card.append(empty);
    }
    content.append(card);

    const delivCard = element("div");
    delivCard.className = "card";
    const delivTitle = element("h3", "Recent Deliveries & Notifications Log");
    delivTitle.style.marginBottom = "15px";
    delivCard.append(delivTitle);

    if (deliveries.items.length) {
      const dt = table(["Time", "Rule ID", "Channel", "Status", "Details/Error"], deliveries.items.map(d => [
        text(d.created_at),
        text(d.rule_id),
        text(d.channel),
        resultBadge(d.status),
        text(d.error_code)
      ]));

      const mobList = element("div");
      mobList.className = "responsive-card-list mobile-only";
      deliveries.items.forEach(d => {
        const c = element("div");
        c.className = "mobile-data-card";
        c.append(
          mobileRow("Time", text(d.created_at)),
          mobileRow("Rule ID", text(d.rule_id)),
          mobileRow("Channel", text(d.channel)),
          mobileRow("Status", resultBadge(d.status)),
          mobileRow("Details/Error", text(d.error_code))
        );
        mobList.append(c);
      });

      delivCard.append(dt, mobList);
    } else {
      const empty = element("div");
      empty.className = "empty-state";
      empty.append(element("div", "No delivery attempts recorded."));
      delivCard.append(empty);
    }

    delivCard.style.marginTop = "24px";
    content.append(delivCard);

  } catch (r) {
    displayError(content, r, () => void renderRules());
  }
}

async function renderOperations() {
  if (!guarded("viewer", "Operations")) return;
  const view = renderShell("Operations & Service Health", "Core service status, log sources, and active firewall blocks");

  const content = element("div");
  view.append(content);

  renderSkeleton(content);

  try {
    const [health, sources, blocks] = await Promise.all([
      api<Record<string, any>>("/operations/health"),
      api<{ items: Array<Record<string, any>> }>("/log-sources"),
      api<{ items: Array<Record<string, any>> }>("/firewall/blocks")
    ]);

    content.replaceChildren();

    const grid = element("div");
    grid.className = "status-grid";

    grid.append(
      createStatusCard("System API Status", health.status),
      createStatusCard("SQLite Database", health.database),
      createStatusCard("Firewall Blocker Daemon", health.firewall?.available ? "available" : "unavailable"),
      createStatusCard("nftables Table Structure", health.firewall?.table_present ? "present" : "missing"),
      createStatusCard("nftables IPv4 Set", health.firewall?.ipv4_set_present ? "present" : "missing"),
      createStatusCard("nftables IPv6 Set", health.firewall?.ipv6_set_present ? "present" : "missing"),
      createStatusCard("Active Blocks count", String(health.active_blocks || 0)),
      createStatusCard("Healthy Log Sources", health.log_sources ? `OK: ${health.log_sources.ok || 0} | Deg: ${health.log_sources.error || 0}` : "Unknown")
    );
    content.append(grid);

    const srcCard = element("div");
    srcCard.className = "card";
    const srcTitle = element("h3", "Log Sources Health");
    srcTitle.style.marginBottom = "15px";
    srcCard.append(srcTitle);

    if (sources.items.length) {
      const dt = table(["Source Name", "Type", "Status", "Last Event", "Today Count", "Parse Errors"], sources.items.map(x => [
        text(x.name),
        text(x.source_type),
        resultBadge(x.status),
        text(x.last_event_at),
        text(x.events_today),
        text(x.parse_errors_today)
      ]));

      const mobList = element("div");
      mobList.className = "responsive-card-list mobile-only";
      sources.items.forEach(x => {
        const c = element("div");
        c.className = "mobile-data-card";
        c.append(
          mobileRow("Name", text(x.name)),
          mobileRow("Type", text(x.source_type)),
          mobileRow("Status", resultBadge(x.status)),
          mobileRow("Last Event", text(x.last_event_at)),
          mobileRow("Today Count", text(x.events_today)),
          mobileRow("Parse Errors", text(x.parse_errors_today))
        );
        mobList.append(c);
      });
      srcCard.append(dt, mobList);
    } else {
      const empty = element("div");
      empty.className = "empty-state";
      empty.append(element("div", "No log sources configured."));
      srcCard.append(empty);
    }
    content.append(srcCard);

    const blocksCard = element("div");
    blocksCard.className = "card";
    const blocksTitle = element("h3", "Active Firewall Blocks");
    blocksTitle.style.marginBottom = "15px";
    blocksCard.append(blocksTitle);

    if (blocks.items.length) {
      const dt = table(["Blocked IP", "Reason", "Blocked At", "Expires At", "Synced Status", "Actions"], blocks.items.map(x => {
        const actions = element("span");
        if (can("admin")) {
          const unblockBtn = button("Unblock IP", () => void requiredReason(`Unblock IP ${text(x.src_ip)}`, async reason => {
            await api(`/firewall/blocks/${encodeURIComponent(text(x.src_ip))}`, {
              method: "DELETE",
              body: JSON.stringify({ reason })
            });
            await renderOperations();
          }));
          unblockBtn.className = "btn btn-danger btn-sm";
          actions.append(unblockBtn);
        } else {
          actions.textContent = "—";
        }

        return [
          text(x.src_ip),
          text(x.reason),
          text(x.blocked_at),
          text(x.expires_at),
          resultBadge(x.firewall_synced ? "Synced" : "Out of sync"),
          actions
        ];
      }));

      const mobList = element("div");
      mobList.className = "responsive-card-list mobile-only";
      blocks.items.forEach(x => {
        const actions = element("div");
        if (can("admin")) {
          const unblockBtn = button("Unblock", () => void requiredReason(`Unblock IP ${text(x.src_ip)}`, async reason => {
            await api(`/firewall/blocks/${encodeURIComponent(text(x.src_ip))}`, {
              method: "DELETE",
              body: JSON.stringify({ reason })
            });
            await renderOperations();
          }));
          unblockBtn.className = "btn btn-danger btn-sm";
          actions.append(unblockBtn);
        } else {
          actions.textContent = "—";
        }

        const c = element("div");
        c.className = "mobile-data-card";
        c.append(
          mobileRow("Blocked IP", text(x.src_ip)),
          mobileRow("Reason", text(x.reason)),
          mobileRow("Blocked At", text(x.blocked_at)),
          mobileRow("Expires At", text(x.expires_at)),
          mobileRow("Synced", resultBadge(x.firewall_synced ? "Synced" : "Out of sync")),
          mobileRow("Actions", actions)
        );
        mobList.append(c);
      });
      blocksCard.append(dt, mobList);
    } else {
      const empty = element("div");
      empty.className = "empty-state";
      empty.append(element("div", "No active firewall blocks."));
      blocksCard.append(empty);
    }

    blocksCard.style.marginTop = "24px";
    content.append(blocksCard);

  } catch (r) {
    displayError(content, r, () => void renderOperations());
  }
}

function createStatusCard(label: string, value: string): HTMLElement {
  const card = element("div");
  card.className = "status-card";

  const header = element("div");
  header.className = "status-card-header";
  header.textContent = label;

  const valDiv = element("div");
  valDiv.className = "status-card-value";
  valDiv.append(resultBadge(value));

  card.append(header, valDiv);
  return card;
}

async function renderAllowlist() {
  if (!guarded("admin", "Allowlist Management")) return;
  const view = renderShell("IP Allowlist Control", "Define network exclusions that are exempt from automated blocks");

  const content = element("div");
  view.append(content);

  renderSkeleton(content);

  try {
    const result = await api<{ items: Array<{ id: number; ip_or_cidr: string; description?: string; enabled?: boolean; created_by?: number; created_at?: string }> }>("/allowlist");
    content.replaceChildren();

    const card = element("div");
    card.className = "card";

    const addBtn = button("Add Allowlist Entry", async () => {
      const ipVal = await showModal("Add Allowlist Entry", "Enter IP address or CIDR range (e.g. 192.168.1.0/24):", true);
      if (!ipVal || !ipVal.trim()) {
        showToast("Valid network address range is required", "warning");
        return;
      }

      await requiredReason(`Add ${ipVal.trim()} to Allowlist`, async reason => {
        await api("/allowlist", {
          method: "POST",
          body: JSON.stringify({ ip_or_cidr: ipVal.trim(), description: reason })
        });
        showToast("Allowlist entry added", "success");
        await renderAllowlist();
      });
    });
    addBtn.style.marginBottom = "20px";
    card.append(addBtn);

    if (result.items.length) {
      const dt = table(["Value / CIDR", "Description", "Created At", "Enabled", "Actions"], result.items.map(x => {
        const actions = element("span");
        const removeBtn = button("Remove", () => void requiredReason(`Remove ${x.ip_or_cidr} from Allowlist`, async reason => {
          await api(`/allowlist/${x.id}`, {
            method: "DELETE",
            body: JSON.stringify({ reason })
          });
          showToast("Allowlist entry removed", "success");
          await renderAllowlist();
        }));
        removeBtn.className = "btn btn-danger btn-sm";
        actions.append(removeBtn);

        return [
          x.ip_or_cidr,
          text(x.description),
          text(x.created_at),
          resultBadge(x.enabled ? "Active" : "Disabled"),
          actions
        ];
      }));
      card.append(dt);
    } else {
      const empty = element("div");
      empty.className = "empty-state";
      empty.append(element("div", "No allowlist entries configured."));
      card.append(empty);
    }
    content.append(card);

  } catch (r) {
    displayError(content, r, () => void renderAllowlist());
  }
}

async function renderAudit() {
  if (!guarded("admin", "Audit Log")) return;
  const view = renderShell("Audit Log Ledger", "System transaction log for configuration modifications and firewall events");

  const content = element("div");
  view.append(content);

  const filters = element("form");
  filters.className = "filters-bar";

  const actor = filterInput("Filter Actor (User)");
  const actionField = filterInput("Filter Action Type");
  const applyBtn = button("Apply Filters", () => void load());

  filters.append(actor, actionField, applyBtn);
  filters.onsubmit = e => {
    e.preventDefault();
    void load();
  };
  content.append(filters);

  const tableContainer = element("div");
  content.append(tableContainer);

  async function load() {
    renderSkeleton(tableContainer);
    try {
      const q = new URLSearchParams({ page_size: "50" });
      if (actor.value.trim()) q.set("actor_username", actor.value.trim());
      if (actionField.value.trim()) q.set("action", actionField.value.trim());

      const result = await api<{ audit_entry_count: number; items: Array<Record<string, any>> }>(`/admin/audit?${q}`);
      tableContainer.replaceChildren();

      const stats = element("p", `${result.audit_entry_count} total logged activities`);
      stats.style.marginBottom = "15px";
      stats.style.color = "var(--text-muted)";
      tableContainer.append(stats);

      if (result.items.length) {
        const dt = table(["Time", "Actor", "Action", "Target", "Result", "Request ID"], result.items.map(x => [
          text(x.created_at),
          text(x.username),
          text(x.action),
          text(x.target_value),
          resultBadge(text(x.result)),
          requestIdElement(text(x.request_id))
        ]));

        const mobList = element("div");
        mobList.className = "responsive-card-list mobile-only";
        result.items.forEach(x => {
          const c = element("div");
          c.className = "mobile-data-card";
          c.append(
            mobileRow("Time", text(x.created_at)),
            mobileRow("Actor", text(x.username)),
            mobileRow("Action", text(x.action)),
            mobileRow("Target", text(x.target_value)),
            mobileRow("Result", resultBadge(text(x.result))),
            mobileRow("Request ID", requestIdElement(text(x.request_id)))
          );
          mobList.append(c);
        });

        tableContainer.append(dt, mobList);
      } else {
        const empty = element("div");
        empty.className = "empty-state";
        empty.append(element("div", "No matching audit ledger entries found."));
        tableContainer.append(empty);
      }
    } catch (r) {
      displayError(tableContainer, r, () => void load());
    }
  }

  await load();
}

async function renderAdmin() {
  if (!guarded("admin", "User Administration")) return;
  const view = renderShell("User Account Management", "Manage credentials, authentication parameters, and role designations");

  const content = element("div");
  view.append(content);

  renderSkeleton(content);

  try {
    const users = await api<User[]>("/admin/users");
    content.replaceChildren();

    if (users.length) {
      const rows = users.map(u => {
        const actionsSpan = element("span");
        if (currentUser && currentUser.id !== u.id) {
          const editBtn = button("Change Role", async () => {
            const newRole = await showModal(`Update Designation`, "Select role (admin, analyst, viewer):", true, u.role);
            if (!newRole) return;
            const roleStr = newRole.trim().toLowerCase();
            if (roleStr !== "admin" && roleStr !== "analyst" && roleStr !== "viewer") {
              showToast("Invalid role. Select admin, analyst, or viewer.", "error");
              return;
            }
            try {
              await api(`/admin/users/${u.id}/role`, {
                method: "PATCH",
                body: JSON.stringify({ role: roleStr })
              });
              showToast(`Role updated successfully for ${u.username}`, "success");
              await renderAdmin();
            } catch (err: any) {
              showToast(err.message || "Failed to change user role", "error");
            }
          });
          editBtn.className = "btn btn-secondary btn-sm";
          actionsSpan.append(editBtn);
        } else {
          const selfBadge = element("span", "Current user session");
          selfBadge.className = "badge neutral";
          actionsSpan.append(selfBadge);
        }

        return [
          u.username,
          text(u.display_name),
          resultBadge(u.role),
          resultBadge("Active"),
          actionsSpan
        ] as Array<string | Node>;
      });

      const dt = table(["Username", "Display Name", "Assigned Role", "Status", "Actions"], rows);

      const mobList = element("div");
      mobList.className = "responsive-card-list mobile-only";
      users.forEach(u => {
        const actions = element("div");
        if (currentUser && currentUser.id !== u.id) {
          const editBtn = button("Change Role", async () => {
            const newRole = await showModal(`Update Designation`, "Select role (admin, analyst, viewer):", true, u.role);
            if (!newRole) return;
            const roleStr = newRole.trim().toLowerCase();
            if (roleStr !== "admin" && roleStr !== "analyst" && roleStr !== "viewer") {
              showToast("Invalid role. Select admin, analyst, or viewer.", "error");
              return;
            }
            try {
              await api(`/admin/users/${u.id}/role`, {
                method: "PATCH",
                body: JSON.stringify({ role: roleStr })
              });
              showToast(`Role updated successfully for ${u.username}`, "success");
              await renderAdmin();
            } catch (err: any) {
              showToast(err.message || "Failed to change user role", "error");
            }
          });
          editBtn.className = "btn btn-secondary btn-sm";
          actions.append(editBtn);
        } else {
          actions.textContent = "Current session";
        }

        const c = element("div");
        c.className = "mobile-data-card";
        c.append(
          mobileRow("Username", u.username),
          mobileRow("Display Name", text(u.display_name)),
          mobileRow("Role", resultBadge(u.role)),
          mobileRow("Status", resultBadge("Active")),
          mobileRow("Actions", actions)
        );
        mobList.append(c);
      });

      content.append(dt, mobList);
    } else {
      const empty = element("div");
      empty.className = "empty-state";
      empty.append(element("div", "No enabled users found."));
      content.append(empty);
    }
  } catch (r) {
    displayError(content, r, () => void renderAdmin());
  }
}

// ---------------------- ROUTER ----------------------

function route() {
  const [page = "dashboard", id] = location.hash.replace(/^#\//, "").split("/");

  if (!token || !currentUser) {
    return renderLogin();
  }

  if (page === "events") void renderEvents();
  else if (page === "event" && id) void renderEvent(id);
  else if (page === "attackers") void renderAttackers();
  else if (page === "attacker" && id) void renderAttacker(decodeURIComponent(id));
  else if (page === "alerts") void renderAlerts();
  else if (page === "rules") void renderRules();
  else if (page === "operations") void renderOperations();
  else if (page === "allowlist") void renderAllowlist();
  else if (page === "audit") void renderAudit();
  else if (page === "admin") void renderAdmin();
  else void renderDashboard();
}

window.addEventListener("hashchange", route);
route();
