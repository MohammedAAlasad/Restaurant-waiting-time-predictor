import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Bar, BarChart, CartesianGrid, Legend, Line, LineChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import {
  AlertTriangle, CheckCheck, Clock, ListOrdered, Loader2, MapPin, Play,
  Plus, Search, Store, Ticket, Users,
} from "lucide-react";

/* ───────────── Config ─────────────
   Set VITE_API_URL (e.g. http://127.0.0.1:8000) to talk to FastAPI.
   Leave it unset to run against the in-memory mock (same interface). */
const API_URL = import.meta.env?.VITE_API_URL || "";
const POLL_MS = 5000;
const STATUS = { CREATED: "CREATED", IN_PROGRESS: "IN_PROGRESS", COMPLETED: "COMPLETED" };

/* ───────────── Geocoding (OpenStreetMap Nominatim) ─────────────
   Usage policy: max 1 request/sec, no autocomplete-as-you-type. Submit on demand only. */
export async function fetchGeocode(address) {
  const q = address.trim();
  if (!q) throw new Error("Enter an address or area first.");
  const url = `https://nominatim.openstreetmap.org/search?format=jsonv2&limit=1&q=${encodeURIComponent(q)}`;
  const res = await fetch(url, { headers: { Accept: "application/json" } });
  if (!res.ok) throw new Error(`Geocoding failed (${res.status}).`);
  const [hit] = await res.json();
  if (!hit) throw new Error("No match found. Try a street address or a nearby landmark.");
  return {
    latitude: parseFloat(hit.lat),
    longitude: parseFloat(hit.lon),
    displayName: hit.display_name,
  };
}

/* ───────────── API layer ───────────── */
async function http(path, options = {}) {
  const res = await fetch(`${API_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed (${res.status})`);
  }
  return res.json();
}

const realApi = {
  async snapshot(geo) {
    const [queue, pred] = await Promise.all([
      http("/queue"), // proposed: { orders: [...], employees_working }
      http("/predict", { method: "POST", body: JSON.stringify(geo ? { latitude: geo.latitude, longitude: geo.longitude } : {}) }),
    ]);
    return { orders: queue.orders, employees: queue.employees_working, predicted: pred.predicted_waiting_time, warnings: pred.warnings || [] };
  },
  createOrder: () => http("/orders", { method: "POST", body: JSON.stringify({}) }), // proposed: returns the order incl. id
  startOrder: (id) => http(`/orders/${id}/start`, { method: "PUT" }),
  completeOrder: (id) => http(`/orders/${id}/complete`, { method: "PUT" }),
  setEmployees: (n) => http("/employees", { method: "PUT", body: JSON.stringify({ employees_working: n }) }),
  analytics: () => http("/analytics/hourly"),
  orderStatus: (id) => http(`/orders/${id}/status`),
  setLocation: (g) => http("/restaurant/location", {
    method: "PUT",
    body: JSON.stringify({ latitude: g.latitude, longitude: g.longitude }),
  }),
};

const mock = { orders: [], employees: 3, nextId: 101 };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const mockApi = {
  async snapshot() {
    await sleep(120);
    const pending = mock.orders.filter((o) => o.status === STATUS.CREATED).length;
    const active = mock.orders.filter((o) => o.status === STATUS.IN_PROGRESS).length;
    const predicted = Math.round((3 + (pending * 5.66 * 0.9 + active * 2) / mock.employees) * 10) / 10;
    return {
      orders: mock.orders.map((o) => ({ ...o })),
      employees: mock.employees,
      predicted,
      warnings: pending > 31 ? ["customers_in_queue is outside the training range"] : [],
    };
  },
  async createOrder() {
    const o = { id: mock.nextId++, status: STATUS.CREATED, created_at: new Date().toISOString() };
    mock.orders.push(o);
    return o;
  },
  async startOrder(id) {
    Object.assign(mock.orders.find((o) => o.id === id), { status: STATUS.IN_PROGRESS, started_at: new Date().toISOString() });
  },
  async completeOrder(id) {
    Object.assign(mock.orders.find((o) => o.id === id), { status: STATUS.COMPLETED, completed_at: new Date().toISOString() });
  },
  async setEmployees(n) { mock.employees = n; },
  async setLocation() {},
  async orderStatus() { return null; },
  async analytics() {
    const hours = [...Array(24).keys()];
    const peak = (h, c, w) => Math.exp(-((h - c) ** 2) / (2 * w * w));
    return {
      hourly_volume: hours.map((h) => Math.round(4 + 38 * peak(h, 12.5, 1.6) + 30 * peak(h, 19, 2))),
      typical_wait: hours.map((h) => Math.round((4 + 14 * peak(h, 12.5, 1.6) + 11 * peak(h, 19, 2)) * 10) / 10),
    };
  },
};
const api = API_URL ? realApi : mockApi;

/* ───────────── Queue hook ───────────── */
function useQueue(geo) {
  const [snap, setSnap] = useState({ orders: [], employees: 3, predicted: 0, warnings: [] });
  const [analytics, setAnalytics] = useState(null);
  const [history, setHistory] = useState([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [ready, setReady] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const s = await api.snapshot(geo);
      setSnap(s);
      setError("");
      const now = new Date();
      setHistory((h) => [...h, { time: now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }), hour: now.getHours(), live: s.predicted }].slice(-30));
    } catch (e) {
      setError(e.message || "Could not reach the server.");
    } finally {
      setReady(true);
    }
  }, [geo]);

  useEffect(() => { api.analytics().then(setAnalytics).catch(() => {}); }, []);
  useEffect(() => {
    refresh();
    // Safety-net poll; with a live backend the SSE stream below does the real work.
    const poll = setInterval(refresh, API_URL ? 60000 : POLL_MS);
    let source;
    if (API_URL && "EventSource" in window) {
      source = new EventSource(`${API_URL}/events`);
      source.addEventListener("update", refresh); // server says: something changed
    }
    return () => { clearInterval(poll); source?.close(); };
  }, [refresh]);

  const run = useCallback(async (fn) => {
    setBusy(true);
    try { const out = await fn(); await refresh(); return out; }
    catch (e) { setError(e.message); }
    finally { setBusy(false); }
  }, [refresh]);

  const byAge = (status) => snap.orders.filter((o) => o.status === status).sort((a, b) => a.id - b.id);
  const actions = {
    create: () => run(() => api.createOrder()),
    startOldest: () => { const o = byAge(STATUS.CREATED)[0]; return o && run(() => api.startOrder(o.id)); },
    completeOldest: () => { const o = byAge(STATUS.IN_PROGRESS)[0]; return o && run(() => api.completeOrder(o.id)); },
    setStaff: (n) => run(() => api.setEmployees(Math.max(1, n))),
  };
  return { snap, analytics, history, error, busy, ready, actions, pending: byAge(STATUS.CREATED), active: byAge(STATUS.IN_PROGRESS) };
}

/* ───────────── UI helpers ───────────── */
const Card = ({ className = "", children }) => (
  <section className={`rounded-2xl border border-slate-200 bg-white p-4 sm:p-5 ${className}`}>{children}</section>
);

const Metric = ({ icon: Icon, label, children }) => (
  <Card className="flex items-start gap-3">
    <span className="rounded-lg bg-teal-50 p-2 text-teal-800"><Icon className="h-5 w-5" aria-hidden /></span>
    <div className="min-w-0">
      <p className="text-sm text-slate-600">{label}</p>
      <div className="text-2xl font-semibold tabular-nums text-slate-900">{children}</div>
    </div>
  </Card>
);

const Btn = ({ icon: Icon, children, tone = "dark", ...props }) => {
  const tones = {
    dark: "bg-slate-900 text-white hover:bg-slate-700",
    teal: "bg-teal-700 text-white hover:bg-teal-800",
    light: "border border-slate-300 bg-white text-slate-900 hover:bg-slate-50",
  };
  return (
    <button
      {...props}
      className={`inline-flex items-center justify-center gap-2 rounded-xl px-4 py-2.5 text-sm font-medium transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-700 disabled:cursor-not-allowed disabled:opacity-40 ${tones[tone]}`}
    >
      <Icon className="h-4 w-4" aria-hidden />{children}
    </button>
  );
};

/* ───────────── Admin view ───────────── */
function AdminView({ q, geo, setGeo }) {
  const { snap, analytics, history, actions, busy, pending, active } = q;
  const [address, setAddress] = useState("");
  const [geoState, setGeoState] = useState({ loading: false, error: "" });

  const lookup = async (e) => {
    e.preventDefault();
    setGeoState({ loading: true, error: "" });
    try { const g = await fetchGeocode(address); await api.setLocation(g); setGeo(g); setGeoState({ loading: false, error: "" }); }
    catch (err) { setGeoState({ loading: false, error: err.message }); }
  };

  const trend = useMemo(
    () => history.map((p) => ({ ...p, typical: analytics?.typical_wait?.[p.hour] ?? null })),
    [history, analytics]
  );
  const volume = useMemo(() => {
    if (!analytics) return [];
    const today = Array(24).fill(0);
    snap.orders.forEach((o) => { today[new Date(o.created_at).getHours()] += 1; });
    return analytics.hourly_volume.map((typical, h) => ({ hour: `${String(h).padStart(2, "0")}:00`, typical, today: today[h] }));
  }, [analytics, snap.orders]);

  return (
    <div className="space-y-4">
      <Card>
        <form onSubmit={lookup} className="flex flex-col gap-3 sm:flex-row">
          <label className="flex-1">
            <span className="mb-1 block text-sm font-medium text-slate-700">Restaurant address or area</span>
            <input
              value={address}
              onChange={(e) => setAddress(e.target.value)}
              placeholder="e.g. 1 Market St, San Francisco"
              className="w-full rounded-xl border border-slate-300 px-3 py-2.5 text-sm focus:border-teal-700 focus:outline-none focus:ring-2 focus:ring-teal-700/30"
            />
          </label>
          <div className="self-end">
            <Btn type="submit" icon={geoState.loading ? Loader2 : Search} tone="teal" disabled={geoState.loading}>
              {geoState.loading ? "Searching…" : "Find coordinates"}
            </Btn>
          </div>
        </form>
        {geoState.error && <p role="alert" className="mt-3 text-sm text-red-700">{geoState.error}</p>}
        {geo && (
          <p className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-slate-700">
            <MapPin className="h-4 w-4 text-teal-700" aria-hidden />
            <span className="tabular-nums">Latitude {geo.latitude.toFixed(5)}</span>
            <span className="tabular-nums">Longitude {geo.longitude.toFixed(5)}</span>
            <span className="w-full truncate text-slate-500 sm:w-auto" title={geo.displayName}>{geo.displayName}</span>
          </p>
        )}
      </Card>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <Metric icon={Users} label="Active staff">
          <div className="flex items-center gap-2">
            <button aria-label="Remove one staff member" onClick={() => actions.setStaff(snap.employees - 1)} disabled={busy || snap.employees <= 1} className="h-8 w-8 rounded-lg border border-slate-300 text-lg leading-none hover:bg-slate-50 disabled:opacity-40">−</button>
            <input
              type="number" min={1} aria-label="Active staff count" value={snap.employees}
              onChange={(e) => actions.setStaff(parseInt(e.target.value || "1", 10))}
              className="w-14 rounded-lg border border-slate-300 py-1 text-center text-xl"
            />
            <button aria-label="Add one staff member" onClick={() => actions.setStaff(snap.employees + 1)} disabled={busy} className="h-8 w-8 rounded-lg border border-slate-300 text-lg leading-none hover:bg-slate-50 disabled:opacity-40">+</button>
          </div>
        </Metric>
        <Metric icon={ListOrdered} label="Orders in queue">
          {pending.length + active.length}
          <span className="ml-2 text-sm font-normal text-slate-500">{pending.length} waiting · {active.length} preparing</span>
        </Metric>
        <Metric icon={Clock} label="Estimated wait">{snap.predicted.toFixed(1)} min</Metric>
      </div>

      {snap.warnings.length > 0 && (
        <p role="status" className="flex items-start gap-2 rounded-xl bg-amber-50 p-3 text-sm text-amber-900">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
          Prediction may be less reliable: {snap.warnings.join("; ")}.
        </p>
      )}

      <Card className="flex flex-col gap-3 sm:flex-row">
        <Btn icon={Plus} tone="teal" onClick={actions.create} disabled={busy}>Create Order</Btn>
        <Btn icon={Play} onClick={actions.startOldest} disabled={busy || !pending.length}>Start Order</Btn>
        <Btn icon={CheckCheck} tone="light" onClick={actions.completeOldest} disabled={busy || !active.length}>Complete Order</Btn>
        <p className="text-sm text-slate-500 sm:ml-auto sm:self-center">
          Start takes the oldest waiting order. Complete finishes the oldest one in preparation.
        </p>
      </Card>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card>
          <h2 className="mb-3 font-semibold text-slate-900">Wait time: live vs. typical for the hour</h2>
          <div className="h-64">
            <ResponsiveContainer>
              <LineChart data={trend} margin={{ left: -16, right: 8, top: 8 }}>
                <CartesianGrid stroke="#e2e8f0" vertical={false} />
                <XAxis dataKey="time" tick={{ fontSize: 12 }} minTickGap={24} />
                <YAxis tick={{ fontSize: 12 }} unit="m" />
                <Tooltip formatter={(v) => `${Number(v).toFixed(1)} min`} />
                <Legend />
                <Line name="Live prediction" dataKey="live" stroke="#0f766e" strokeWidth={2.5} dot={false} isAnimationActive={false} />
                <Line name="Typical" dataKey="typical" stroke="#64748b" strokeDasharray="5 4" dot={false} isAnimationActive={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </Card>
        <Card>
          <h2 className="mb-3 font-semibold text-slate-900">Orders per hour</h2>
          <div className="h-64">
            <ResponsiveContainer>
              <BarChart data={volume} margin={{ left: -16, right: 8, top: 8 }}>
                <CartesianGrid stroke="#e2e8f0" vertical={false} />
                <XAxis dataKey="hour" tick={{ fontSize: 12 }} interval={3} />
                <YAxis tick={{ fontSize: 12 }} />
                <Tooltip />
                <Legend />
                <Bar name="Typical" dataKey="typical" fill="#cbd5e1" radius={[3, 3, 0, 0]} />
                <Bar name="Today" dataKey="today" fill="#0f766e" radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
      </div>
    </div>
  );
}

/* ───────────── Customer view ───────────── */
function CustomerView({ q }) {
  const { snap, pending, active, actions, busy } = q;
  const open = [...active, ...pending].sort((a, b) => a.id - b.id);
  const [pick, setPick] = useState(null);
  const ticket = snap.orders.find((o) => o.id === pick) || open[open.length - 1] || null;
  const [status, setStatus] = useState(null);
  useEffect(() => {
    if (!API_URL || !ticket) return;
    api.orderStatus(ticket.id).then(setStatus).catch(() => {});
  }, [ticket?.id, snap.orders]);

  const view = useMemo(() => {
    if (!ticket) return null;
    if (ticket.status === STATUS.COMPLETED) return { state: "ready" };
    if (ticket.status === STATUS.IN_PROGRESS) return { state: "preparing", ahead: 0, eta: Math.max(1, Math.round(snap.predicted * 0.3)) };
    const ahead = active.length + pending.filter((o) => o.id < ticket.id).length;
    const total = Math.max(1, pending.length);
    const fallback = snap.predicted * (pending.filter((o) => o.id <= ticket.id).length / total);
    const mid = Math.max(1, status && status.id === ticket.id ? status.eta_minutes : fallback);
    return { state: "waiting", ahead, lo: Math.max(1, Math.round(mid * 0.85)), hi: Math.max(2, Math.round(mid * 1.15)) };
  }, [ticket, snap.predicted, pending, active, status]);

  const take = async () => { const o = await actions.create(); if (o?.id) setPick(o.id); };

  return (
    <div className="mx-auto max-w-md">
      {!ticket ? (
        <Card className="py-12 text-center">
          <Ticket className="mx-auto mb-3 h-8 w-8 text-slate-400" aria-hidden />
          <p className="mb-4 text-slate-700">No active tickets. Get one to see your wait.</p>
          <Btn icon={Plus} tone="teal" onClick={take} disabled={busy}>Get a ticket</Btn>
        </Card>
      ) : (
        <Card className="overflow-hidden !p-0">
          <div className="border-b border-dashed border-slate-300 bg-slate-900 px-6 py-5 text-white">
            <p className="text-sm text-slate-300">Your ticket</p>
            <p className="text-5xl font-bold tabular-nums">#{ticket.id}</p>
          </div>
          <div className="space-y-5 p-6">
            {view.state === "waiting" && (
              <>
                <div>
                  <p className="text-sm text-slate-600">Estimated wait</p>
                  <p className="text-4xl font-semibold tabular-nums text-teal-800">{view.lo}–{view.hi} minutes</p>
                </div>
                <p className="text-lg text-slate-800">
                  {view.ahead === 0 ? "You're next" : `${view.ahead} order${view.ahead === 1 ? "" : "s"} ahead`}
                </p>
              </>
            )}
            {view.state === "preparing" && (
              <>
                <p className="text-3xl font-semibold text-teal-800">Being prepared</p>
                <p className="text-slate-700">About {view.eta} more minute{view.eta === 1 ? "" : "s"}.</p>
              </>
            )}
            {view.state === "ready" && <p className="text-3xl font-semibold text-teal-800">Ready for pickup</p>}
            <div className="flex items-center justify-between gap-3 border-t border-slate-200 pt-4">
              {open.length > 1 ? (
                <label className="text-sm text-slate-600">
                  Track ticket{" "}
                  <select value={ticket.id} onChange={(e) => setPick(Number(e.target.value))} className="ml-1 rounded-lg border border-slate-300 px-2 py-1">
                    {open.map((o) => <option key={o.id} value={o.id}>#{o.id}</option>)}
                  </select>
                </label>
              ) : <span />}
              <Btn icon={Plus} tone="light" onClick={take} disabled={busy}>New ticket</Btn>
            </div>
          </div>
        </Card>
      )}
    </div>
  );
}

/* ───────────── App ───────────── */
export default function App() {
  const [tab, setTab] = useState("admin");
  const [geo, setGeo] = useState(null);
  const q = useQueue(geo);
  const tabs = [{ id: "admin", label: "Restaurant", icon: Store }, { id: "customer", label: "Customer", icon: Ticket }];

  return (
    <div className="min-h-screen bg-slate-100 text-slate-900">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-4 py-3">
          <h1 className="text-lg font-semibold">TimePred</h1>
          <nav role="tablist" aria-label="View" className="flex rounded-xl bg-slate-100 p-1">
            {tabs.map(({ id, label, icon: Icon }) => (
              <button
                key={id} role="tab" aria-selected={tab === id} onClick={() => setTab(id)}
                className={`inline-flex items-center gap-2 rounded-lg px-4 py-1.5 text-sm font-medium focus-visible:outline focus-visible:outline-2 focus-visible:outline-teal-700 ${tab === id ? "bg-white shadow-sm" : "text-slate-600 hover:text-slate-900"}`}
              >
                <Icon className="h-4 w-4" aria-hidden />{label}
              </button>
            ))}
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-6xl space-y-4 px-4 py-6">
        {!API_URL && <p className="rounded-xl bg-slate-200 p-3 text-sm text-slate-700">Demo mode: data is simulated in the browser. Set VITE_API_URL to use your FastAPI backend.</p>}
        {q.error && <p role="alert" className="rounded-xl bg-red-50 p-3 text-sm text-red-800">{q.error}</p>}
        {!q.ready ? (
          <p className="flex items-center gap-2 text-slate-600"><Loader2 className="h-4 w-4 animate-spin" aria-hidden />Loading queue…</p>
        ) : tab === "admin" ? <AdminView q={q} geo={geo} setGeo={setGeo} /> : <CustomerView q={q} />}
      </main>
    </div>
  );
}
