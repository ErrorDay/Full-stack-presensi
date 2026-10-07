import { useEffect, useState } from "react";
import { api, STATUS_DOT } from "@/lib/api";
import { Users, UserCheck, Clock, FileText, UserX, AlertCircle } from "lucide-react";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, Legend } from "recharts";

const PIE_COLORS = { "Hadir": "#059669", "Terlambat": "#D97706", "Izin": "#2563EB", "Alpa": "#DC2626", "Belum": "#9CA3AF" };

export default function Dashboard() {
  const [stats, setStats] = useState(null);

  useEffect(() => {
    api.get("/dashboard/stats").then((r) => setStats(r.data)).catch(() => {});
  }, []);

  if (!stats) return <div className="text-sm text-[#6B7280]" data-testid="dashboard-loading">Memuat dashboard...</div>;

  const cards = [
    { label: "Total Siswa", value: stats.total_students, icon: Users, color: "text-[#1D4ED8]", bg: "bg-blue-50", testid: "stat-total-siswa" },
    { label: "Hadir Hari Ini", value: stats.hadir, icon: UserCheck, color: "text-emerald-600", bg: "bg-emerald-50", testid: "stat-hadir" },
    { label: "Terlambat", value: stats.terlambat, icon: Clock, color: "text-amber-600", bg: "bg-amber-50", testid: "stat-terlambat" },
    { label: "Izin", value: stats.izin, icon: FileText, color: "text-blue-600", bg: "bg-blue-50", testid: "stat-izin" },
    { label: "Alpa", value: stats.alpa, icon: UserX, color: "text-red-600", bg: "bg-red-50", testid: "stat-alpa" },
    { label: "Belum Presensi", value: stats.belum_presensi, icon: AlertCircle, color: "text-gray-500", bg: "bg-gray-100", testid: "stat-belum" },
  ];

  const pieData = [
    { name: "Hadir", value: stats.hadir - stats.terlambat },
    { name: "Terlambat", value: stats.terlambat },
    { name: "Izin", value: stats.izin },
    { name: "Alpa", value: stats.alpa },
    { name: "Belum", value: stats.belum_presensi },
  ].filter((d) => d.value > 0);

  return (
    <div className="space-y-8" data-testid="dashboard-page">
      <div>
        <h1 className="text-3xl font-bold text-[#111827]">Dashboard</h1>
        <p className="text-sm text-[#6B7280] mt-1">Ringkasan presensi sekolah · {stats.date}</p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-5">
        {cards.map((c) => {
          const Icon = c.icon;
          return (
            <div key={c.label} data-testid={c.testid} className="bg-white border border-[#E5E7EB] rounded-xl p-5 shadow-sm hover:-translate-y-0.5 hover:shadow-md transition-transform duration-150">
              <div className={`w-9 h-9 rounded-lg ${c.bg} flex items-center justify-center mb-4`}>
                <Icon className={`w-4.5 h-4.5 w-5 h-5 ${c.color}`} />
              </div>
              <p className="text-3xl font-bold font-mono text-[#111827]">{c.value}</p>
              <p className="text-xs text-[#6B7280] mt-1">{c.label}</p>
            </div>
          );
        })}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        <div className="lg:col-span-2 bg-white border border-[#E5E7EB] rounded-xl p-6 shadow-sm" data-testid="chart-trend">
          <h2 className="text-lg font-semibold text-[#111827] mb-1">Tren Presensi 7 Hari Terakhir</h2>
          <p className="text-xs text-[#6B7280] mb-6">Jumlah siswa per status setiap hari</p>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={stats.trend}>
              <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" vertical={false} />
              <XAxis dataKey="label" tick={{ fontSize: 12, fill: "#6B7280" }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fontSize: 12, fill: "#6B7280" }} axisLine={false} tickLine={false} />
              <Tooltip />
              <Bar dataKey="Hadir" stackId="a" fill="#059669" radius={[0, 0, 0, 0]} />
              <Bar dataKey="Izin" stackId="a" fill="#2563EB" />
              <Bar dataKey="Alpa" stackId="a" fill="#DC2626" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="bg-white border border-[#E5E7EB] rounded-xl p-6 shadow-sm" data-testid="chart-komposisi">
          <h2 className="text-lg font-semibold text-[#111827] mb-1">Komposisi Hari Ini</h2>
          <p className="text-xs text-[#6B7280] mb-4">Distribusi status kehadiran</p>
          <ResponsiveContainer width="100%" height={260}>
            <PieChart>
              <Pie data={pieData} dataKey="value" nameKey="name" innerRadius={55} outerRadius={85} paddingAngle={3}>
                {pieData.map((d) => <Cell key={d.name} fill={PIE_COLORS[d.name]} />)}
              </Pie>
              <Legend iconSize={10} wrapperStyle={{ fontSize: 12 }} />
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </div>

        <div className="bg-white border border-[#E5E7EB] rounded-xl p-6 shadow-sm" data-testid="recent-activity">
          <h2 className="text-lg font-semibold text-[#111827] mb-1">Presensi Terbaru</h2>
          <p className="text-xs text-[#6B7280] mb-4">Aktivitas pemindaian terakhir</p>
          <div className="space-y-3">
            {stats.recent.length === 0 && <p className="text-sm text-[#6B7280]">Belum ada data presensi.</p>}
            {stats.recent.map((r) => (
              <div key={r.id} className="flex items-center gap-3">
                <span className={`w-2 h-2 rounded-full shrink-0 ${STATUS_DOT[r.status] || "bg-gray-400"}`} />
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium text-[#111827] truncate">{r.name}</p>
                  <p className="text-[11px] text-[#6B7280]">{r.class_name} · {r.status}</p>
                </div>
                <span className="text-[11px] font-mono text-[#6B7280] shrink-0">{r.time?.slice(0, 5)}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
