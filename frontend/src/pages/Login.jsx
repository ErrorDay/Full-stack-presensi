import { useState } from "react";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";

export default function Login() {
  const { login } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!username || !password) return;

    setSubmitting(true);
    try {
      await login(username, password);
    } catch (err) {
      toast.error(err.response?.data?.detail || "Username atau password salah.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#FAFAFA] px-4">
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-sm bg-white border border-[#E5E7EB] rounded-xl p-8 shadow-sm"
        data-testid="login-form"
      >
        <div className="flex flex-col items-center mb-6">
          <img
            src="/logo-sekolah.png"
            alt="Logo Sekolah"
            className="w-14 h-14 object-contain mb-2"
          />
          <p className="font-heading font-bold text-lg text-[#111827]">SI-PRESENSI</p>
          <p className="text-sm text-[#6B7280]">Masuk untuk melanjutkan</p>
        </div>

        <div className="mb-4">
          <label className="block text-sm font-medium text-[#111827] mb-1">Username</label>
          <input
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            className="w-full px-3 py-2 border border-[#E5E7EB] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#1D4ED8]"
            autoFocus
            data-testid="login-username"
          />
        </div>

        <div className="mb-6">
          <label className="block text-sm font-medium text-[#111827] mb-1">Password</label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full px-3 py-2 border border-[#E5E7EB] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#1D4ED8]"
            data-testid="login-password"
          />
        </div>

        <Button
          type="submit"
          disabled={submitting}
          className="w-full bg-[#1D4ED8] hover:bg-[#1e40af] text-white"
          data-testid="login-submit"
        >
          {submitting ? "Memproses..." : "Masuk"}
        </Button>
      </form>
    </div>
  );
}
