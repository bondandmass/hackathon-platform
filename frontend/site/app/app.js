"use strict";

const CFG = window.APP_CONFIG;
const MAX_TEAM = 4;
const CRITERIA = [
  { key: "innovation", label: "Innovation", weight: 0.3, color: "var(--c1)" },
  { key: "technical", label: "Technical depth", weight: 0.3, color: "var(--c2)" },
  { key: "impact", label: "Impact", weight: 0.25, color: "var(--c3)" },
  { key: "presentation", label: "Presentation", weight: 0.15, color: "var(--c4)" },
];

// Lucide icon paths (ISC licence), drawn inline so there is no icon font or extra request.
const ICONS = {
  users: '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
  upload: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" x2="12" y1="3" y2="15"/>',
  download: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" x2="12" y1="15" y2="3"/>',
  star: '<polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>',
  trophy: '<path d="M6 9H4.5a2.5 2.5 0 0 1 0-5H6"/><path d="M18 9h1.5a2.5 2.5 0 0 0 0-5H18"/><path d="M4 22h16"/><path d="M10 14.66V17c0 .55-.47.98-.97 1.21C7.85 18.75 7 20.24 7 22"/><path d="M14 14.66V17c0 .55.47.98.97 1.21C16.15 18.75 17 20.24 17 22"/><path d="M18 2H6v7a6 6 0 0 0 12 0V2Z"/>',
  logout: '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" x2="9" y1="12" y2="12"/>',
  link: '<path d="M15 3h6v6"/><path d="M10 14 21 3"/><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>',
  file: '<path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/><polyline points="14 2 14 8 20 8"/>',
  check: '<polyline points="20 6 9 17 4 12"/>',
  alert: '<circle cx="12" cy="12" r="10"/><line x1="12" x2="12" y1="8" y2="12"/><line x1="12" x2="12.01" y1="16" y2="16"/>',
  plus: '<path d="M5 12h14"/><path d="M12 5v14"/>',
  clock: '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>',
};
const icon = (name, label) => `<svg class="icon" viewBox="0 0 24 24" ${label ? `role="img" aria-label="${label}"` : 'aria-hidden="true"'}>${ICONS[name]}</svg>`;

const $ = (sel, root = document) => root.querySelector(sel);
const main = $("#main");
let refreshTimer = null;

/* ---------- helpers ---------- */

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
const safeUrl = (url) => (/^https?:\/\//i.test(url || "") ? url : "");
const initials = (name) => String(name).trim().split(/\s+/).slice(0, 2).map((w) => w[0]).join("").toUpperCase() || "?";
const weighted = (v) => CRITERIA.reduce((sum, c) => sum + v[c.key] * c.weight, 0);

function toast(message, bad = false) {
  const el = $("#toast");
  el.innerHTML = `${icon(bad ? "alert" : "check")}<span>${esc(message)}</span>`;
  el.classList.toggle("bad", bad);
  el.classList.add("show");
  clearTimeout(toast.t);
  toast.t = setTimeout(() => el.classList.remove("show"), bad ? 5000 : 3000);
}

function formatBytes(n) {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

function decodeJwt(token) {
  const part = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
  return JSON.parse(atob(part + "=".repeat((4 - (part.length % 4)) % 4)));
}

// Shows a spinner in the button while the work runs and keeps its width steady.
async function busy(button, work, busyLabel) {
  const html = button.innerHTML;
  button.style.minWidth = `${button.offsetWidth}px`;
  button.disabled = true;
  button.setAttribute("aria-busy", "true");
  button.innerHTML = `<span class="spinner" aria-hidden="true"></span>${busyLabel ? `<span>${esc(busyLabel)}</span>` : '<span class="sr-only">Working</span>'}`;
  try {
    return await work();
  } finally {
    if (button.isConnected) {
      button.disabled = false;
      button.removeAttribute("aria-busy");
      button.innerHTML = html;
      button.style.minWidth = "";
    }
  }
}

function confirmDialog({ title, body, action }) {
  const dlg = $("#confirm");
  $("#confirm-title").textContent = title;
  $("#confirm-body").textContent = body;
  $("#confirm-yes").textContent = action;
  return new Promise((resolve) => {
    const done = (ok) => { dlg.close(); resolve(ok); };
    $("#confirm-yes").onclick = () => done(true);
    $("#confirm-no").onclick = () => done(false);
    dlg.oncancel = (e) => { e.preventDefault(); done(false); };
    dlg.showModal();
    $("#confirm-no").focus();
  });
}

function setFieldError(input, message) {
  const err = document.getElementById(`${input.id}-error`);
  input.setAttribute("aria-invalid", message ? "true" : "false");
  if (err) err.innerHTML = message ? `${icon("alert")}<span>${esc(message)}</span>` : "";
  return !message;
}

function field({ id, name, label, type = "text", hint, attrs = "", textarea = false, value = "" }) {
  const describedBy = [hint ? `${id}-hint` : "", `${id}-error`].filter(Boolean).join(" ");
  const control = textarea
    ? `<textarea id="${id}" name="${name}" aria-describedby="${describedBy}" ${attrs}>${esc(value)}</textarea>`
    : `<input id="${id}" name="${name}" type="${type}" value="${esc(value)}" aria-describedby="${describedBy}" ${attrs}>`;
  return `<div class="field">
    <label for="${id}">${label}</label>
    ${hint ? `<span class="hint" id="${id}-hint">${hint}</span>` : ""}
    ${control}
    <p class="field-error" id="${id}-error"></p>
  </div>`;
}

function skeleton() {
  main.setAttribute("aria-busy", "true");
  main.innerHTML = `<div class="skeleton" aria-hidden="true"><i class="h"></i><i></i><i class="b"></i><i class="b"></i></div><span class="sr-only">Loading</span>`;
}

function emptyState(iconName, title, body, actionHtml = "") {
  return `<div class="empty">${icon(iconName)}<strong>${title}</strong><p>${body}</p>${actionHtml}</div>`;
}

/* ---------- session (Cognito) ---------- */

const session = {
  cache: null,
  get() {
    if (session.cache) return session.cache;
    try { session.cache = JSON.parse(sessionStorage.getItem("hp.session")); } catch { session.cache = null; }
    return session.cache;
  },
  set(value) {
    session.cache = value;
    try { sessionStorage.setItem("hp.session", JSON.stringify(value)); } catch { /* storage blocked: keep in memory */ }
  },
  clear() {
    session.cache = null;
    try { sessionStorage.removeItem("hp.session"); } catch { /* storage blocked */ }
  },
};

async function cognito(action, body) {
  const res = await fetch(`https://cognito-idp.${CFG.region}.amazonaws.com/`, {
    method: "POST",
    headers: { "Content-Type": "application/x-amz-json-1.1", "X-Amz-Target": `AWSCognitoIdentityProviderService.${action}` },
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const type = (data.__type || "").split("#").pop();
    const messages = {
      NotAuthorizedException: "That email and password don't match. Check both and try again.",
      UserNotFoundException: "That email and password don't match. Check both and try again.",
      PasswordResetRequiredException: "This account needs a password reset. Ask an organiser.",
      UserNotConfirmedException: "This account isn't confirmed yet. Ask an organiser.",
      InvalidPasswordException: data.message || "That password doesn't meet the rules.",
      TooManyRequestsException: "Too many attempts. Wait a minute and try again.",
    };
    throw new Error(messages[type] || data.message || "Sign-in failed. Try again.");
  }
  return data;
}

function storeTokens(result, refreshToken) {
  const claims = decodeJwt(result.AccessToken);
  session.set({ access: result.AccessToken, refresh: result.RefreshToken || refreshToken, exp: claims.exp, sub: claims.sub, groups: claims["cognito:groups"] || [] });
}

async function accessToken() {
  const s = session.get();
  if (!s) return null;
  if (s.exp - Date.now() / 1000 > 60) return s.access;
  try {
    const data = await cognito("InitiateAuth", { AuthFlow: "REFRESH_TOKEN_AUTH", ClientId: CFG.clientId, AuthParameters: { REFRESH_TOKEN: s.refresh } });
    storeTokens(data.AuthenticationResult, s.refresh);
    return session.get().access;
  } catch {
    signOut("Your session ended. Sign in again.");
    return null;
  }
}

function signOut(message) {
  session.clear();
  clearInterval(refreshTimer);
  location.hash = "";
  render();
  if (message) toast(message);
}

/* ---------- API ---------- */

class ApiError extends Error {
  constructor(status, message) { super(message); this.status = status; }
}

async function api(path, { method = "GET", json, form } = {}) {
  const token = await accessToken();
  if (!token) throw new ApiError(401, "Not signed in");
  const headers = { Authorization: `Bearer ${token}` };
  let body;
  if (json !== undefined) { headers["Content-Type"] = "application/json"; body = JSON.stringify(json); }
  if (form) body = form;
  let res;
  try {
    res = await fetch(path, { method, headers, body });
  } catch {
    throw new ApiError(0, "Can't reach the server. Check your connection");
  }
  if (res.status === 401) { signOut("Your session ended. Sign in again."); throw new ApiError(401, "Session ended"); }
  if (res.status === 204) return null;
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    let detail = data && data.detail;
    if (Array.isArray(detail)) detail = detail.map((d) => d.msg).join("; ");
    throw new ApiError(res.status, detail || `Request failed (${res.status})`);
  }
  return data;
}

async function myTeam() {
  try { return await api("/teams/me"); } catch (err) { if (err.status === 404) return null; throw err; }
}

async function teamNames() {
  const teams = await api("/teams");
  return Object.fromEntries(teams.map((t) => [t.id, t.name]));
}

/* ---------- layout ---------- */

function me() {
  const s = session.get();
  if (!s) return null;
  return { sub: s.sub, judge: s.groups.includes("judges"), participant: s.groups.includes("participants") };
}

function tabsFor(user) {
  const tabs = [];
  if (user.participant) tabs.push(["team", "My team", "users"], ["submission", "Submission", "upload"]);
  if (user.judge) tabs.push(["score", "Score projects", "star"]);
  tabs.push(["leaderboard", "Leaderboard", "trophy"]);
  return tabs;
}

function currentView(user) {
  const ids = tabsFor(user).map(([id]) => id);
  const hash = location.hash.replace("#", "");
  return ids.includes(hash) ? hash : ids[0];
}

function render() {
  clearInterval(refreshTimer);
  const user = me();
  $("#who").hidden = !user;
  $("#tabs").hidden = !user;
  if (!user) { renderSignIn(); return; }

  $("#role").textContent = user.judge && user.participant ? "Judge and participant" : user.judge ? "Judge" : user.participant ? "Participant" : "No role yet";
  const view = currentView(user);
  $("#tabs").innerHTML = tabsFor(user)
    .map(([id, label, ic]) => `<button type="button" data-view="${id}" ${id === view ? 'aria-current="page"' : ""}>${icon(ic)}<span>${label}</span></button>`)
    .join("");

  if (!user.judge && !user.participant) {
    main.innerHTML = emptyState("alert", "Your account isn't in a group yet", "Ask an organiser to add you to participants or judges, then sign in again.");
    return;
  }
  const views = { team: viewTeam, submission: viewSubmission, score: viewScore, leaderboard: viewLeaderboard };
  skeleton();
  views[view](user)
    .catch((err) => {
      if (err.status === 401) return;
      main.innerHTML = emptyState("alert", "This page couldn't load", `${esc(err.message)}.`, `<button class="btn secondary" type="button" id="retry">Try again</button>`);
      $("#retry").addEventListener("click", render);
    })
    .finally(() => main.removeAttribute("aria-busy"));
}

/* ---------- sign in ---------- */

function renderSignIn(challenge) {
  main.innerHTML = `
    <section class="signin">
      <div class="signin-hero">
        <div class="blocks" aria-hidden="true"><i></i><i></i><i></i><i></i><i></i><i></i></div>
        <div class="copy">
          <h1>Build it, ship it, get scored.</h1>
          <p>Sign in with the email and password the organisers gave you. What you see depends on your role.</p>
          <ul class="roles">
            <li>${icon("users")}<div><strong>Participants</strong>Form a team of up to four and upload your project.</div></li>
            <li>${icon("star")}<div><strong>Judges</strong>Score each project on four criteria. The leaderboard updates live.</div></li>
          </ul>
        </div>
      </div>
      <form class="signin-form fields" id="signin-form" novalidate>
        ${challenge ? `
          <h2>Choose a new password</h2>
          <p class="meta">This is your first sign-in, so set your own password.</p>
          ${field({ id: "new-password", name: "newPassword", label: "New password", type: "password", hint: "At least 8 characters with upper and lower case, a number and a symbol", attrs: 'autocomplete="new-password" required' })}
        ` : `
          <h2>Sign in</h2>
          ${field({ id: "email", name: "email", label: "Email", type: "email", attrs: 'autocomplete="username" inputmode="email" required' })}
          ${field({ id: "password", name: "password", label: "Password", type: "password", attrs: 'autocomplete="current-password" required' })}
        `}
        <div class="field-error" id="signin-error" role="alert"></div>
        <button class="btn block" type="submit">${challenge ? "Set password and sign in" : "Sign in"}</button>
      </form>
    </section>`;

  const form = $("#signin-form");
  form.querySelector("input").focus();
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const errorEl = $("#signin-error");
    errorEl.innerHTML = "";
    let ok = true;
    if (challenge) {
      const np = $("#new-password");
      ok = setFieldError(np, np.value.length < 8 ? "Use at least 8 characters." : "");
    } else {
      const email = $("#email");
      const pw = $("#password");
      ok = setFieldError(email, !email.value.trim() ? "Enter your email." : !email.checkValidity() ? "Enter a valid email, like name@example.com." : "") & setFieldError(pw, pw.value ? "" : "Enter your password.");
    }
    if (!ok) { form.querySelector("[aria-invalid=true]").focus(); return; }

    await busy(form.querySelector("button[type=submit]"), async () => {
      try {
        let result;
        if (challenge) {
          result = await cognito("RespondToAuthChallenge", {
            ChallengeName: "NEW_PASSWORD_REQUIRED", ClientId: CFG.clientId, Session: challenge.session,
            ChallengeResponses: { USERNAME: challenge.username, NEW_PASSWORD: $("#new-password").value },
          });
        } else {
          const email = $("#email").value.trim();
          result = await cognito("InitiateAuth", { AuthFlow: "USER_PASSWORD_AUTH", ClientId: CFG.clientId, AuthParameters: { USERNAME: email, PASSWORD: $("#password").value } });
          if (result.ChallengeName === "NEW_PASSWORD_REQUIRED") { renderSignIn({ session: result.Session, username: email }); return; }
        }
        storeTokens(result.AuthenticationResult);
        location.hash = "";
        render();
        main.focus();
      } catch (err) {
        errorEl.innerHTML = `${icon("alert")}<span>${esc(err.message)}</span>`;
      }
    }, "Signing in");
  });
}

/* ---------- participant: team ---------- */

async function viewTeam(user) {
  const team = await myTeam();
  if (team) {
    const open = MAX_TEAM - team.members.length;
    main.innerHTML = `
      <div class="page-head">
        <div class="team-hero">
          <div class="avatar" aria-hidden="true">${esc(initials(team.name))}</div>
          <div><h1>${esc(team.name)}</h1>${team.description ? `<p>${esc(team.description)}</p>` : ""}</div>
        </div>
      </div>
      <div class="grid-2">
        <section class="panel" aria-labelledby="members-h">
          <div class="panel-head"><h2 id="members-h">Members</h2><span class="tag">${team.members.length} of ${MAX_TEAM}</span></div>
          <ul class="members">
            ${team.members.map((m) => `<li><span class="chip" aria-hidden="true">${m.user_sub === user.sub ? "Y" : esc(m.user_sub.slice(0, 1).toUpperCase())}</span>
              <span>${m.user_sub === user.sub ? "<strong>You</strong>" : `Member ${esc(m.user_sub.slice(0, 8))}`}</span>
              ${m.role === "leader" ? '<span class="tag lead">Leader</span>' : ""}</li>`).join("")}
            ${Array.from({ length: open }, () => `<li><span class="chip empty" aria-hidden="true">${icon("plus")}</span><span class="meta">Open seat</span></li>`).join("")}
          </ul>
        </section>
        <section class="panel stack" aria-labelledby="invite-h">
          <h2 id="invite-h">Add teammates</h2>
          <p class="meta">${open ? `Teammates sign in, open My team and choose <strong>${esc(team.name)}</strong> from the list.` : "Your team is full."}</p>
          <div class="actions"><a class="btn" href="#submission">${icon("upload")}Go to submission</a>
          <button class="btn danger" id="leave" type="button">${icon("logout")}Leave team</button></div>
        </section>
      </div>`;
    $("#leave").addEventListener("click", async (e) => {
      const last = team.members.length === 1;
      const ok = await confirmDialog({
        title: last ? `Leave and delete ${team.name}?` : `Leave ${team.name}?`,
        body: last ? "You're the only member, so the team will be deleted. Withdraw any submission first." : "You can join another team afterwards. If you're the leader, the longest-standing member takes over.",
        action: last ? "Leave and delete" : "Leave team",
      });
      if (!ok) return;
      busy($("#leave"), async () => {
        try {
          await api(`/teams/${team.id}/leave`, { method: "POST" });
          toast(last ? "You left and the team was deleted" : "You left the team");
          render();
        } catch (err) { toast(err.message, true); }
      });
    });
    return;
  }

  const teams = await api("/teams");
  const withSpace = teams.filter((t) => t.member_count < MAX_TEAM);
  main.innerHTML = `
    <div class="page-head"><div><h1>Find your team</h1><p>You're not in a team yet. Start one, or join a team that has an open seat.</p></div></div>
    <div class="grid-2">
      <section class="panel" aria-labelledby="join-h">
        <div class="panel-head"><h2 id="join-h">Teams with space</h2><span class="tag">${withSpace.length}</span></div>
        ${withSpace.length ? `<ul class="team-list">
          ${withSpace.map((t) => `<li><div><div class="name">${esc(t.name)}</div>
            <div class="seats" role="img" aria-label="${t.member_count} of ${MAX_TEAM} seats taken">${Array.from({ length: MAX_TEAM }, (_, i) => `<i class="${i < t.member_count ? "on" : ""}"></i>`).join("")}</div></div>
            <button class="btn secondary" type="button" data-join="${t.id}" aria-label="Join ${esc(t.name)}">Join</button></li>`).join("")}
        </ul>` : `<p class="meta" style="margin-top:12px">No teams with open seats yet. Create the first one.</p>`}
      </section>
      <form class="panel fields" id="create-team" novalidate aria-labelledby="create-h">
        <h2 id="create-h">Create a team</h2>
        ${field({ id: "team-name", name: "name", label: "Team name", attrs: 'maxlength="100" required' })}
        ${field({ id: "team-desc", name: "description", label: "Description", hint: "Optional", textarea: true, attrs: 'maxlength="1000"' })}
        <button class="btn" type="submit">${icon("plus")}Create team</button>
      </form>
    </div>`;

  $("#create-team").addEventListener("submit", (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const name = $("#team-name");
    if (!setFieldError(name, name.value.trim().length < 2 ? "Use at least 2 characters." : "")) { name.focus(); return; }
    busy(form.querySelector("button[type=submit]"), async () => {
      try {
        await api("/teams", { method: "POST", json: { name: name.value.trim(), description: $("#team-desc").value } });
        toast("Team created");
        render();
      } catch (err) {
        if (err.status === 409) setFieldError(name, err.message); else toast(err.message, true);
      }
    }, "Creating");
  });
  main.querySelectorAll("[data-join]").forEach((btn) => btn.addEventListener("click", () => busy(btn, async () => {
    try {
      await api(`/teams/${btn.dataset.join}/join`, { method: "POST" });
      toast("You joined the team");
      render();
    } catch (err) { toast(err.message, true); }
  })));
}

/* ---------- participant: submission ---------- */

async function viewSubmission() {
  const team = await myTeam();
  if (!team) {
    main.innerHTML = `<div class="page-head"><h1>Submission</h1></div>
      ${emptyState("users", "Join a team first", "Submissions belong to a team. Create or join one, then come back here.", '<a class="btn" href="#team">Go to My team</a>')}`;
    return;
  }

  const [sub] = await api("/submissions");
  if (sub) {
    main.innerHTML = `
      <div class="page-head"><div><span class="tag ok">${icon("check")} Submitted</span><h1 style="margin-top:12px">${esc(sub.title)}</h1>
        <p>Submitted for ${esc(team.name)} on ${new Date(sub.created_at).toLocaleString([], { dateStyle: "medium", timeStyle: "short" })}.</p></div></div>
      <section class="panel stack">
        ${sub.description ? `<p>${esc(sub.description)}</p>` : ""}
        <div class="meta-row"><span>${icon("file")}${esc(sub.filename)}</span><span>${formatBytes(sub.size_bytes)}</span>
          ${safeUrl(sub.repo_url) ? `<span>${icon("link")}<a href="${esc(sub.repo_url)}" target="_blank" rel="noopener">Repository</a></span>` : ""}</div>
        <div class="actions">
          <button class="btn secondary" id="download" type="button">${icon("download")}Download file</button>
          <button class="btn danger" id="withdraw" type="button">Withdraw submission</button>
        </div>
      </section>`;
    $("#download").addEventListener("click", (e) => download(e.currentTarget, sub.id));
    $("#withdraw").addEventListener("click", async (e) => {
      const ok = await confirmDialog({
        title: "Withdraw this submission?",
        body: "The file is deleted and your team can submit again. Scores judges have already given stay on the leaderboard under the old title, so only withdraw before judging starts.",
        action: "Withdraw",
      });
      if (!ok) return;
      busy($("#withdraw"), async () => {
        try {
          await api(`/submissions/${sub.id}`, { method: "DELETE" });
          toast("Submission withdrawn");
          render();
        } catch (err) { toast(err.message, true); }
      });
    });
    return;
  }

  main.innerHTML = `
    <div class="page-head"><div><h1>Submit your project</h1><p>One submission per team. Any member of ${esc(team.name)} can submit or withdraw it.</p></div></div>
    <form class="panel fields" id="submit-form" novalidate>
      ${field({ id: "title", name: "title", label: "Project title", attrs: 'maxlength="200" required' })}
      ${field({ id: "description", name: "description", label: "What it does", hint: "Optional. Two or three sentences for the judges.", textarea: true, attrs: 'maxlength="5000"' })}
      ${field({ id: "repo", name: "repo_url", label: "Repository link", type: "url", hint: "Optional", attrs: 'placeholder="https://github.com/your-team/project"' })}
      <div class="field">
        <span class="label" id="file-label">Project file</span>
        <label class="drop" id="drop">
          <input id="file" type="file" name="file" required aria-labelledby="file-label" aria-describedby="file-status file-error">
          ${icon("upload")}
          <span id="file-status"><strong>Choose a file</strong> or drop it here<br><span class="hint">Slides, a PDF or a zip, up to 20 MB</span></span>
        </label>
        <p class="field-error" id="file-error"></p>
      </div>
      <div class="actions"><button class="btn" type="submit">${icon("upload")}Submit project</button></div>
    </form>`;

  const fileInput = $("#file");
  const drop = $("#drop");
  const showFile = () => {
    const f = fileInput.files[0];
    $("#file-status").innerHTML = f ? `<strong>${esc(f.name)}</strong><br><span class="hint">${formatBytes(f.size)}. Choose again to replace.</span>` : `<strong>Choose a file</strong> or drop it here<br><span class="hint">Slides, a PDF or a zip, up to 20 MB</span>`;
    if (f) setFieldError(fileInput, f.size > 20 * 1024 * 1024 ? "That file is over 20 MB." : "");
  };
  fileInput.addEventListener("change", showFile);
  ["dragenter", "dragover"].forEach((t) => drop.addEventListener(t, () => drop.classList.add("over")));
  ["dragleave", "drop"].forEach((t) => drop.addEventListener(t, () => drop.classList.remove("over")));

  $("#submit-form").addEventListener("submit", (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const title = $("#title");
    const repo = $("#repo");
    const f = fileInput.files[0];
    const ok = setFieldError(title, title.value.trim().length < 2 ? "Give your project a title of at least 2 characters." : "")
      & setFieldError(repo, repo.value && !safeUrl(repo.value) ? "Start the link with https://" : "")
      & setFieldError(fileInput, !f ? "Choose a file to upload." : f.size > 20 * 1024 * 1024 ? "That file is over 20 MB." : "");
    if (!ok) { form.querySelector("[aria-invalid=true]").focus(); return; }
    busy(form.querySelector("button[type=submit]"), async () => {
      try {
        await api("/submissions", { method: "POST", form: new FormData(form) });
        toast("Project submitted");
        render();
      } catch (err) { toast(err.message, true); }
    }, "Uploading");
  });
}

async function download(button, id) {
  await busy(button, async () => {
    try {
      const { url } = await api(`/submissions/${id}/download`);
      window.open(url, "_blank", "noopener");
    } catch (err) { toast(err.message, true); }
  });
}

/* ---------- judge: scoring ---------- */

async function viewScore(user) {
  const [subs, scores, names] = await Promise.all([api("/submissions"), api("/judging/scores"), teamNames()]);
  const mine = Object.fromEntries(scores.filter((s) => s.judge_sub === user.sub).map((s) => [s.submission_id, s]));
  if (!subs.length) {
    main.innerHTML = `<div class="page-head"><h1>Score projects</h1></div>${emptyState("clock", "No submissions yet", "Projects appear here as teams submit them.")}`;
    return;
  }
  // Unscored first, so the next job is always at the top.
  subs.sort((a, b) => (mine[a.id] ? 1 : 0) - (mine[b.id] ? 1 : 0) || a.id - b.id);

  main.innerHTML = `
    <div class="page-head">
      <div><h1>Score projects</h1><p>Rate each criterion from 1 to 10. Saving again replaces your score.</p></div>
      <div class="progress"><span class="meta" id="progress-text"></span><div class="track"><div class="fill" id="progress-fill"></div></div></div>
    </div>
    <div class="stack">${subs.map((s) => scoreCard(s, names[s.team_id], mine[s.id])).join("")}</div>`;

  const updateProgress = () => {
    const done = Object.keys(mine).length;
    $("#progress-text").textContent = `You've scored ${done} of ${subs.length}`;
    $("#progress-fill").style.width = `${(done / subs.length) * 100}%`;
  };
  updateProgress();

  main.querySelectorAll("form[data-score]").forEach((form) => {
    const total = form.querySelector(".live-total strong");
    const recalc = () => {
      const v = Object.fromEntries(CRITERIA.map((c) => [c.key, Number(form.elements[c.key].value)]));
      total.textContent = weighted(v).toFixed(2);
    };
    form.querySelectorAll("input[type=range]").forEach((input) => input.addEventListener("input", () => {
      input.closest(".slider").querySelector("output").value = input.value;
      recalc();
    }));
    recalc();
    form.querySelector("[data-download]").addEventListener("click", (e) => download(e.currentTarget, form.dataset.score));
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      const body = { submission_id: Number(form.dataset.score), comment: form.elements.comment.value || "" };
      CRITERIA.forEach((c) => { body[c.key] = Number(form.elements[c.key].value); });
      busy(form.querySelector("button[type=submit]"), async () => {
        try {
          const saved = await api("/judging/scores", { method: "POST", json: body });
          mine[saved.submission_id] = saved;
          form.querySelector(".status").innerHTML = `<span class="tag ok">${icon("check")} Saved ${saved.total.toFixed(2)}</span>`;
          updateProgress();
          toast("Score saved");
        } catch (err) { toast(err.message, true); }
      }, "Saving");
    });
  });
}

function scoreCard(sub, teamName, existing) {
  return `
    <form class="panel score-card" data-score="${sub.id}" aria-labelledby="sub-${sub.id}">
      <div class="panel-head">
        <div>
          <span class="status">${existing ? `<span class="tag ok">${icon("check")} Your score ${existing.total.toFixed(2)}</span>` : '<span class="tag">Not scored yet</span>'}</span>
          <h2 id="sub-${sub.id}" style="margin-top:10px">${esc(sub.title)}</h2>
          <p class="meta">${esc(teamName || `Team ${sub.team_id}`)}</p>
        </div>
        <div class="live-total" aria-live="polite"><strong>0.00</strong><span class="meta">weighted total</span></div>
      </div>
      ${sub.description ? `<p style="margin-top:12px">${esc(sub.description)}</p>` : ""}
      <div class="actions" style="margin-top:16px">
        <button class="btn secondary" type="button" data-download="${sub.id}">${icon("download")}Download ${esc(sub.filename)}</button>
        ${safeUrl(sub.repo_url) ? `<a class="btn secondary" href="${esc(sub.repo_url)}" target="_blank" rel="noopener">${icon("link")}Open repository</a>` : ""}
      </div>
      <div class="sliders">
        ${CRITERIA.map((c) => {
          const value = existing ? existing[c.key] : 5;
          const id = `s${sub.id}-${c.key}`;
          return `<div class="slider">
            <div class="top"><label for="${id}" class="label">${c.label} <span class="weight">${Math.round(c.weight * 100)}%</span></label><output for="${id}">${value}</output></div>
            <input id="${id}" type="range" name="${c.key}" min="1" max="10" step="1" value="${value}">
          </div>`;
        }).join("")}
      </div>
      <div style="margin-top:20px">${field({ id: `c${sub.id}`, name: "comment", label: "Comment for the team", hint: "Optional", textarea: true, attrs: 'maxlength="2000"', value: existing ? existing.comment : "" })}</div>
      <div class="actions"><button class="btn" type="submit">${icon("star")}Save score</button></div>
    </form>`;
}

/* ---------- leaderboard ---------- */

async function viewLeaderboard() {
  const draw = async () => {
    const [rows, names] = await Promise.all([api("/judging/leaderboard"), teamNames()]);
    const updated = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
    const team = (r) => esc(names[r.team_id] || `Team ${r.team_id}`);
    main.innerHTML = `
      <div class="page-head">
        <div><h1>Leaderboard</h1><p>Average weighted score across judges, out of 10.</p></div>
        <span class="live"><span class="pulse" aria-hidden="true"></span>Live, updated ${updated}</span>
      </div>
      ${rows.length ? `
        <div class="legend" aria-hidden="true">${CRITERIA.map((c) => `<span><i style="background:${c.color}"></i>${c.label} ${Math.round(c.weight * 100)}%</span>`).join("")}</div>
        <ol class="board">
          ${rows.map((r) => `
            <li class="r${r.rank}">
              <span class="rank">${r.rank}<span class="sr-only"> place</span></span>
              <div><div class="title">${esc(r.title)}</div><div class="team">${team(r)}</div></div>
              <div class="score">${r.average_total.toFixed(2)}<small>${r.judges} ${r.judges === 1 ? "judge" : "judges"}</small></div>
              <div class="bar" aria-hidden="true">${CRITERIA.map((c) => `<span style="width:${(r[c.key] * c.weight * 10).toFixed(2)}%;background:${c.color}"></span>`).join("")}</div>
              <div class="breakdown">${CRITERIA.map((c) => `<span>${c.label} ${r[c.key].toFixed(1)}</span>`).join("")}</div>
            </li>`).join("")}
        </ol>` : emptyState("trophy", "No scores yet", "Rankings appear as soon as a judge scores a project.")}`;
  };
  await draw();
  refreshTimer = setInterval(() => { if (!document.hidden) draw().catch(() => {}); }, 15000);
}

/* ---------- boot ---------- */

$("#signout").innerHTML = `${icon("logout")}<span>Sign out</span>`;
$("#signout").addEventListener("click", () => signOut("Signed out"));
$("#tabs").addEventListener("click", (event) => {
  const btn = event.target.closest("[data-view]");
  if (btn) location.hash = btn.dataset.view;
});
window.addEventListener("hashchange", () => { render(); main.focus({ preventScroll: true }); });
document.title = CFG.eventName;
$("#brand").textContent = CFG.eventName;
render();
