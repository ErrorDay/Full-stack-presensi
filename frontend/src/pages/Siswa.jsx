import { useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { Search, Pencil, Trash2, UserPlus, ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

const EMPTY = { nisn: "", name: "", gender: "L", class_id: "" };

export default function Siswa() {
  const [students, setStudents] = useState([]);
  const [classes, setClasses] = useState([]);
  const [q, setQ] = useState("");
  const [classFilter, setClassFilter] = useState("all");
  const [dialog, setDialog] = useState(null); // {mode, data}
  const [page, setPage] = useState(1);
  const PER_PAGE = 20;

  const load = useCallback(async () => {
    const params = {};
    if (q) params.q = q;
    if (classFilter !== "all") params.class_id = classFilter;
    const r = await api.get("/students", { params });
    setStudents(r.data);
  }, [q, classFilter]);

  useEffect(() => {
    api.get("/classes").then((r) => setClasses(r.data)).catch(() => {});
  }, []);

  useEffect(() => {
    const t = setTimeout(() => load().catch(() => {}), 250);
    return () => clearTimeout(t);
  }, [load]);

  useEffect(() => { setPage(1); }, [q, classFilter]);

  const totalPages = Math.max(1, Math.ceil(students.length / PER_PAGE));
  const paged = students.slice((page - 1) * PER_PAGE, page * PER_PAGE);

  const save = async () => {
    const d = dialog.data;
    if (!d.nisn || !d.name) { toast.error("NIS/NISN dan nama wajib diisi"); return; }
    try {
      if (dialog.mode === "add") {
        await api.post("/students", d);
        toast.success("Siswa terdaftar");
      } else {
        await api.put(`/students/${d.id}`, d);
        toast.success("Data siswa diperbarui");
      }
      setDialog(null);
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Gagal menyimpan siswa");
    }
  };

  const remove = async (s) => {
    if (!window.confirm(`Hapus siswa ${s.name}?`)) return;
    await api.delete(`/students/${s.id}`);
    toast.success("Siswa dihapus");
    load();
  };

  return (
    <div className="space-y-8" data-testid="siswa-page">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-3xl font-bold text-[#111827]">Siswa</h1>
          <p className="text-sm text-[#6B7280] mt-1">Pendaftaran dan pengelolaan seluruh siswa sekolah</p>
        </div>
        <Button data-testid="siswa-add-btn" onClick={() => setDialog({ mode: "add", data: { ...EMPTY } })} className="bg-[#1D4ED8] hover:bg-[#1E40AF]">
          <UserPlus className="w-4 h-4 mr-2" /> Daftarkan Siswa
        </Button>
      </div>

      <div className="bg-white border border-[#E5E7EB] rounded-xl shadow-sm">
        <div className="flex flex-wrap items-end gap-4 px-6 py-5 border-b border-[#E5E7EB]">
          <div className="flex-1 min-w-64">
            <Label className="text-xs">Pencarian</Label>
            <div className="relative mt-1.5">
              <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-[#9CA3AF]" />
              <Input data-testid="siswa-search-input" className="pl-9" placeholder="Cari nama atau NIS/NISN..." value={q} onChange={(e) => setQ(e.target.value)} />
            </div>
          </div>
          <div>
            <Label className="text-xs">Kelas</Label>
            <Select value={classFilter} onValueChange={setClassFilter}>
              <SelectTrigger data-testid="siswa-filter-kelas" className="mt-1.5 w-48"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Semua Kelas</SelectItem>
                <SelectItem value="none">Belum Ada Kelas</SelectItem>
                {classes.map((c) => <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <p className="text-xs text-[#6B7280] pb-2.5 ml-auto">{students.length} siswa ditemukan</p>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-sm" data-testid="siswa-table">
            <thead>
              <tr className="text-left text-xs text-[#6B7280] border-b border-[#E5E7EB] bg-[#F9FAFB]">
                <th className="px-6 py-3 font-medium w-12">No</th>
                <th className="px-6 py-3 font-medium">NIS/NISN</th>
                <th className="px-6 py-3 font-medium">Nama</th>
                <th className="px-6 py-3 font-medium">L/P</th>
                <th className="px-6 py-3 font-medium">Kelas</th>
                <th className="px-6 py-3 font-medium">Status</th>
                <th className="px-6 py-3 font-medium text-right">Aksi</th>
              </tr>
            </thead>
            <tbody>
              {paged.map((s, i) => (
                <tr key={s.id} data-testid={`siswa-row-${s.id}`} className="border-b border-[#F3F4F6] last:border-0 hover:bg-[#F9FAFB] transition-colors duration-100">
                  <td className="px-6 py-3.5 font-mono text-xs text-[#6B7280]">{(page - 1) * PER_PAGE + i + 1}</td>
                  <td className="px-6 py-3.5 font-mono text-xs">{s.nisn}</td>
                  <td className="px-6 py-3.5 font-medium text-[#111827]">{s.name}</td>
                  <td className="px-6 py-3.5 text-[#6B7280]">{s.gender}</td>
                  <td className="px-6 py-3.5">
                    {s.class_name ? (
                      <span className="text-xs px-2 py-1 rounded-full bg-blue-50 text-blue-700 border border-blue-200">{s.class_name}</span>
                    ) : (
                      <span className="text-xs px-2 py-1 rounded-full bg-gray-100 text-gray-500 border border-gray-200">Belum ada kelas</span>
                    )}
                  </td>
                  <td className="px-6 py-3.5">
                    <span className="text-xs px-2 py-1 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200">{s.status}</span>
                  </td>
                  <td className="px-6 py-3.5 text-right">
                    <div className="flex justify-end gap-1">
                      <button data-testid={`edit-siswa-${s.id}`} title="Ubah" className="p-2 rounded-lg hover:bg-gray-100 text-[#6B7280] transition-colors duration-100"
                        onClick={() => setDialog({ mode: "edit", data: { ...s, class_id: s.class_id || "" } })}>
                        <Pencil className="w-4 h-4" />
                      </button>
                      <button data-testid={`delete-siswa-${s.id}`} title="Hapus" className="p-2 rounded-lg hover:bg-red-50 text-red-500 transition-colors duration-100"
                        onClick={() => remove(s)}>
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
              {paged.length === 0 && (
                <tr><td colSpan={7} className="px-6 py-10 text-center text-sm text-[#6B7280]">Tidak ada siswa yang cocok dengan pencarian.</td></tr>
              )}
            </tbody>
          </table>
        </div>

        <div className="flex items-center justify-between px-6 py-4 border-t border-[#E5E7EB]" data-testid="siswa-pagination">
          <p className="text-xs text-[#6B7280]">
            Menampilkan <span className="font-mono font-medium text-[#111827]">{paged.length}</span> dari <span className="font-mono font-medium text-[#111827]">{students.length}</span> siswa
          </p>
          <div className="flex items-center gap-2">
            <Button data-testid="pagination-prev" variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
              <ChevronLeft className="w-4 h-4 mr-1" /> Sebelumnya
            </Button>
            <div className="flex items-center gap-1">
              {Array.from({ length: totalPages }, (_, i) => i + 1).map((n) => (
                <button
                  key={n}
                  data-testid={`pagination-page-${n}`}
                  onClick={() => setPage(n)}
                  className={`w-8 h-8 rounded-lg text-xs font-mono font-medium transition-colors duration-150 ${
                    n === page ? "bg-[#1D4ED8] text-white" : "text-[#6B7280] hover:bg-[#F3F4F6]"
                  }`}
                >
                  {n}
                </button>
              ))}
            </div>
            <Button data-testid="pagination-next" variant="outline" size="sm" disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>
              Berikutnya <ChevronRight className="w-4 h-4 ml-1" />
            </Button>
          </div>
        </div>
      </div>

      <Dialog open={!!dialog} onOpenChange={() => setDialog(null)}>
        <DialogContent data-testid="siswa-dialog">
          <DialogHeader><DialogTitle>{dialog?.mode === "add" ? "Daftarkan Siswa Baru" : "Ubah Data Siswa"}</DialogTitle></DialogHeader>
          <div className="space-y-4 py-2">
            <div>
              <Label>NIS/NISN</Label>
              <Input data-testid="siswa-nisn-input" className="mt-1.5" value={dialog?.data.nisn || ""}
                onChange={(e) => setDialog((p) => ({ ...p, data: { ...p.data, nisn: e.target.value } }))} />
            </div>
            <div>
              <Label>Nama Lengkap</Label>
              <Input data-testid="siswa-name-input" className="mt-1.5" value={dialog?.data.name || ""}
                onChange={(e) => setDialog((p) => ({ ...p, data: { ...p.data, name: e.target.value } }))} />
            </div>
            <div>
              <Label>Jenis Kelamin</Label>
              <Select value={dialog?.data.gender || "L"} onValueChange={(v) => setDialog((p) => ({ ...p, data: { ...p.data, gender: v } }))}>
                <SelectTrigger data-testid="siswa-gender-select" className="mt-1.5"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="L">Laki-laki</SelectItem>
                  <SelectItem value="P">Perempuan</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label>Kelas (opsional)</Label>
              <Select value={dialog?.data.class_id || "none"} onValueChange={(v) => setDialog((p) => ({ ...p, data: { ...p.data, class_id: v === "none" ? "" : v } }))}>
                <SelectTrigger data-testid="siswa-class-select" className="mt-1.5"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">Belum ada kelas</SelectItem>
                  {classes.map((c) => <SelectItem key={c.id} value={c.id}>{c.name} (Kelas {c.grade})</SelectItem>)}
                </SelectContent>
              </Select>
              <p className="text-[11px] text-[#6B7280] mt-1.5">Kelas bisa dikosongkan — siswa dapat dimasukkan ke kelas nanti melalui tab Kelas.</p>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialog(null)}>Batal</Button>
            <Button data-testid="siswa-save-btn" onClick={save} className="bg-[#1D4ED8] hover:bg-[#1E40AF]">Simpan</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
