import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { Save, Plus, X, ScanFace, Database } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

const HARI = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"];

export default function Pengaturan() {
  const [s, setS] = useState(null);
  const [liburInput, setLiburInput] = useState("");

  useEffect(() => {
    api.get("/settings").then((r) => setS(r.data)).catch(() => {});
  }, []);

  if (!s) return <div className="text-sm text-[#6B7280]" data-testid="settings-loading">Memuat pengaturan...</div>;

  const save = async () => {
    try {
      const r = await api.put("/settings", {
        jam_masuk: s.jam_masuk,
        batas_terlambat_menit: Number(s.batas_terlambat_menit),
        hari_sekolah: s.hari_sekolah,
        hari_libur: s.hari_libur,
        fr_mode: s.fr_mode,
        fr_endpoint_url: s.fr_endpoint_url,
      });
      setS(r.data);
      toast.success("Pengaturan disimpan");
    } catch {
      toast.error("Gagal menyimpan pengaturan");
    }
  };

  const toggleHari = (i) => {
    setS((p) => ({
      ...p,
      hari_sekolah: p.hari_sekolah.includes(i) ? p.hari_sekolah.filter((d) => d !== i) : [...p.hari_sekolah, i].sort(),
    }));
  };

  const addLibur = () => {
    if (!liburInput || s.hari_libur.includes(liburInput)) return;
    setS((p) => ({ ...p, hari_libur: [...p.hari_libur, liburInput].sort() }));
    setLiburInput("");
  };

  return (
    <div className="space-y-8" data-testid="pengaturan-page">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-3xl font-bold text-[#111827]">Pengaturan</h1>
          <p className="text-sm text-[#6B7280] mt-1">Konfigurasi sistem presensi, jadwal sekolah, dan modul Face Recognition</p>
        </div>
        <Button data-testid="save-settings-btn" onClick={save} className="bg-[#1D4ED8] hover:bg-[#1E40AF]">
          <Save className="w-4 h-4 mr-2" /> Simpan Pengaturan
        </Button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white border border-[#E5E7EB] rounded-xl shadow-sm p-6" data-testid="settings-presensi">
          <h2 className="text-lg font-semibold text-[#111827] mb-1">Konfigurasi Presensi</h2>
          <p className="text-xs text-[#6B7280] mb-6">Menentukan status Tidak Terlambat / Terlambat secara otomatis</p>
          <div className="space-y-5">
            <div>
              <Label>Jam Masuk Sekolah</Label>
              <Input data-testid="jam-masuk-input" type="time" className="mt-1.5 w-44 font-mono" value={s.jam_masuk}
                onChange={(e) => setS((p) => ({ ...p, jam_masuk: e.target.value }))} />
            </div>
            <div>
              <Label>Batas Keterlambatan (menit)</Label>
              <Input data-testid="batas-terlambat-input" type="number" min="0" className="mt-1.5 w-44 font-mono" value={s.batas_terlambat_menit}
                onChange={(e) => setS((p) => ({ ...p, batas_terlambat_menit: e.target.value }))} />
              <p className="text-[11px] text-[#6B7280] mt-1.5">Siswa dianggap terlambat jika presensi melebihi jam masuk + batas ini.</p>
            </div>
          </div>
        </div>

        <div className="bg-white border border-[#E5E7EB] rounded-xl shadow-sm p-6" data-testid="settings-jadwal">
          <h2 className="text-lg font-semibold text-[#111827] mb-1">Hari Sekolah & Hari Libur</h2>
          <p className="text-xs text-[#6B7280] mb-6">Digunakan untuk perhitungan rekap bulanan</p>
          <div className="grid grid-cols-2 gap-3 mb-6">
            {HARI.map((h, i) => (
              <label key={h} className="flex items-center gap-2.5 text-sm text-[#111827] cursor-pointer" data-testid={`hari-check-${i}`}>
                <Checkbox checked={s.hari_sekolah.includes(i)} onCheckedChange={() => toggleHari(i)} />
                {h}
              </label>
            ))}
          </div>
          <Label>Tanggal Hari Libur</Label>
          <div className="flex gap-2 mt-1.5">
            <Input data-testid="libur-input" type="date" className="w-44 font-mono" value={liburInput} onChange={(e) => setLiburInput(e.target.value)} />
            <Button data-testid="libur-add-btn" variant="outline" size="sm" onClick={addLibur}><Plus className="w-4 h-4 mr-1" /> Tambah</Button>
          </div>
          <div className="flex flex-wrap gap-2 mt-3">
            {s.hari_libur.map((d) => (
              <span key={d} className="inline-flex items-center gap-1.5 text-xs font-mono bg-red-50 text-red-700 border border-red-200 rounded-full px-3 py-1">
                {d}
                <button data-testid={`libur-remove-${d}`} onClick={() => setS((p) => ({ ...p, hari_libur: p.hari_libur.filter((x) => x !== d) }))}>
                  <X className="w-3 h-3" />
                </button>
              </span>
            ))}
            {s.hari_libur.length === 0 && <p className="text-xs text-[#6B7280]">Belum ada hari libur khusus.</p>}
          </div>
        </div>

        <div className="bg-white border border-[#E5E7EB] rounded-xl shadow-sm p-6" data-testid="settings-fr">
          <div className="flex items-center gap-3 mb-1">
            <ScanFace className="w-5 h-5 text-[#1D4ED8]" />
            <h2 className="text-lg font-semibold text-[#111827]">Modul Face Recognition</h2>
          </div>
          <p className="text-xs text-[#6B7280] mb-6">Koneksi ke program Face Recognition Python Anda</p>
          <div className="space-y-5">
            <div>
              <Label>Mode Integrasi</Label>
              <Select value={s.fr_mode} onValueChange={(v) => setS((p) => ({ ...p, fr_mode: v }))}>
                <SelectTrigger data-testid="fr-mode-select" className="mt-1.5"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="endpoint">Endpoint API (modul memanggil POST /api/attendance/recognize)</SelectItem>
                  <SelectItem value="local">Modul Lokal (face_recognition_bridge.py di backend)</SelectItem>
                  <SelectItem value="disabled">Nonaktif</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label>URL Endpoint Modul (opsional)</Label>
              <Input data-testid="fr-endpoint-input" className="mt-1.5 font-mono text-xs" placeholder="cth: http://localhost:5000/recognize" value={s.fr_endpoint_url}
                onChange={(e) => setS((p) => ({ ...p, fr_endpoint_url: e.target.value }))} />
            </div>
            <div className="bg-[#F9FAFB] border border-[#E5E7EB] rounded-lg p-4 text-xs text-[#6B7280] leading-relaxed">
              Letakkan program Python Anda di <span className="font-mono text-[#111827]">/app/backend/</span>, lalu hubungkan melalui fungsi
              <span className="font-mono text-[#111827]"> recognize_face()</span> di <span className="font-mono text-[#111827]">face_recognition_bridge.py</span>.
              Data wajah siswa tersimpan di field <span className="font-mono text-[#111827]">face_encoding</span> pada data siswa.
            </div>
          </div>
        </div>

        <div className="bg-white border border-[#E5E7EB] rounded-xl shadow-sm p-6" data-testid="settings-db">
          <div className="flex items-center gap-3 mb-1">
            <Database className="w-5 h-5 text-[#1D4ED8]" />
            <h2 className="text-lg font-semibold text-[#111827]">Database</h2>
          </div>
          <p className="text-xs text-[#6B7280] mb-6">Informasi penyimpanan data</p>
          <div className="space-y-3 text-sm">
            <div className="flex justify-between"><span className="text-[#6B7280] text-xs">Engine</span><span className="font-medium">MongoDB</span></div>
            <div className="flex justify-between"><span className="text-[#6B7280] text-xs">Nama Database</span><span className="font-mono text-xs font-medium">{s.db_name}</span></div>
            <div className="flex justify-between"><span className="text-[#6B7280] text-xs">Koleksi</span><span className="font-mono text-xs font-medium">students · classes · attendance · settings</span></div>
          </div>
        </div>
      </div>
    </div>
  );
}
