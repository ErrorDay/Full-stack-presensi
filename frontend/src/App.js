import { useEffect, useState } from "react";
import "@/App.css";
import { ScanFace, LayoutDashboard, Settings, Users, ClipboardList, GraduationCap, LogOut } from "lucide-react";
import { Toaster } from "@/components/ui/sonner";
import { Button } from "@/components/ui/button";
import { AuthProvider, useAuth } from "@/context/AuthContext";
import Login from "@/pages/Login";
import Dashboard from "@/pages/Dashboard";
import Kelas from "@/pages/Kelas";
import Siswa from "@/pages/Siswa";
import Presensi from "@/pages/Presensi";
import Pengaturan from "@/pages/Pengaturan";

const TABS = [
  { key: "dashboard", label: "Dashboard", icon: LayoutDashboard },
  { key: "pengaturan", label: "Pengaturan", icon: Settings },
  { key: "kelas", label: "Kelas", icon: Users },
  { key: "siswa", label: "Siswa", icon: GraduationCap },
  { key: "presensi", label: "Presensi", icon: ClipboardList },
];

// Tab yang boleh dilihat tiap role. Proteksi SEBENARNYA tetap di
// backend (require_role di tiap endpoint) -- ini cuma supaya user
// tidak melihat menu yang memang bukan wewenangnya.
const ROLE_TABS = {
  admin: ["dashboard", "pengaturan", "kelas", "siswa", "presensi"],
  operator: ["dashboard", "presensi"],
  walas: ["dashboard", "kelas", "siswa", "presensi"],
};

function MainApp() {
  const { user, logout } = useAuth();
  const allowedKeys = ROLE_TABS[user.role] || ["dashboard"];
  const visibleTabs = TABS.filter((t) => allowedKeys.includes(t.key));

  const [tab, setTab] = useState(visibleTabs[0]?.key || "dashboard");

  useEffect(() => {
    // kalau tab yang aktif ternyata bukan wewenang role ini (mis. baru
    // login sebagai operator setelah sebelumnya admin), pindah ke tab
    // pertama yang diizinkan.
    if (!allowedKeys.includes(tab)) {
      setTab(visibleTabs[0]?.key || "dashboard");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user.role]);

  return (
    <div className="min-h-screen bg-[#FAFAFA]">
      <header className="sticky top-0 z-40 bg-white border-b border-[#E5E7EB]">
        <div className="max-w-[1600px] mx-auto px-6 flex items-center gap-8 h-16">
          <div className="flex items-center gap-3 pr-4">
            <img src="/logo-sekolah.png" alt="Logo Sekolah" className="w-10 h-10 object-contain" data-testid="school-logo" />
            <div>
              <p className="font-heading font-bold text-[15px] leading-tight text-[#111827]">SI-PRESENSI</p>
              <p className="text-[11px] text-[#6B7280] leading-tight">SMAIT AL HARAKI</p>
            </div>
          </div>

          <nav className="flex items-center gap-1 flex-1" data-testid="main-nav">
            {visibleTabs.map((t) => {
              const Icon = t.icon;
              const active = tab === t.key;
              return (
                <button
                  key={t.key}
                  data-testid={`nav-${t.key}`}
                  onClick={() => setTab(t.key)}
                  className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors duration-150 ${
                    active
                      ? "bg-[#1D4ED8] text-white"
                      : "text-[#6B7280] hover:text-[#111827] hover:bg-[#F3F4F6]"
                  }`}
                >
                  <Icon className="w-4 h-4" />
                  {t.label}
                </button>
              );
            })}
          </nav>

          <div className="flex items-center gap-3">
            <div className="text-right leading-tight">
              <p className="text-sm font-medium text-[#111827]">{user.nama || user.username}</p>
              <p className="text-[11px] text-[#6B7280] capitalize">{user.role}</p>
            </div>
            <Button
              variant="ghost"
              size="icon"
              onClick={logout}
              title="Keluar"
              data-testid="logout-button"
            >
              <LogOut className="w-4 h-4" />
            </Button>
          </div>
        </div>
      </header>

      <main className="max-w-[1600px] mx-auto px-6 py-8">
        {tab === "dashboard" && <Dashboard />}
        {tab === "pengaturan" && <Pengaturan />}
        {tab === "kelas" && <Kelas />}
        {tab === "siswa" && <Siswa />}
        {tab === "presensi" && <Presensi />}
      </main>
      <Toaster position="top-right" richColors />
    </div>
  );
}

function AppGate() {
  const { user, loading } = useAuth();

  if (loading) {
    return <div className="min-h-screen flex items-center justify-center bg-[#FAFAFA] text-[#6B7280] text-sm">Memuat...</div>;
  }

  if (!user) {
    return <Login />;
  }

  return <MainApp />;
}

function App() {
  return (
    <AuthProvider>
      <AppGate />
    </AuthProvider>
  );
}

export default App;
