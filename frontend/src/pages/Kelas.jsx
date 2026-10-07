import { useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { ChevronDown, ChevronRight, Plus, Pencil, Trash2, ArrowRightLeft, ArrowLeft, UserPlus, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

const GRADES = [10, 11, 12];
const EMPTY_STUDENT = { nisn: "", name: "", gender: "L", class_id: "" };

export default function Kelas() {
  const [classes, setClasses] = useState([]);
  const [students, setStudents] = useState([]);
  const [selected, setSelected] = useState(null);
  const [collapsed, setCollapsed] = useState({});
  const [classDialog, setClassDialog] = useState(null); // {mode, grade, id, name}
  const [studentDialog, setStudentDialog] = useState(null); // {mode, data}
  const [migrateDialog, setMigrateDialog] = useState(null); // student
  const [migrateTarget, setMigrateTarget] = useState("");
  const [allStudents, setAllStudents] = useState([]);

  // Helper untuk mengekstrak pesan error FastAPI / Pydantic agar React tidak crash
  const parseErrorMessage = (error, defaultMsg) => {
    const detail = error.response?.data?.detail;
    if (Array.isArray(detail)) {
      return detail.map((e) => `${e.loc[e.loc.length - 1]}: ${e.msg}`).join(", ");
    }
    if (typeof detail === "object" && detail !== null) {
      return JSON.stringify(detail);
    }
    return detail || defaultMsg;
  };

  const loadClasses = useCallback(async () => {
    const r = await api.get("/classes");
    setClasses(r.data);
    return r.data;
  }, []);

  const loadStudents = useCallback(async (classId) => {
    const r = await api.get("/students", { params: { class_id: classId } });
    setStudents(r.data);
  }, []);

  useEffect(() => {
    loadClasses().then((list) => {
      const col = {};
      list.forEach((c) => { if (!c.visible) col[c.grade] = true; });
      setCollapsed(col);
    }).catch(() => {});
  }, [loadClasses]);

  const toggleGrade = async (grade) => {
    const next = !collapsed[grade];
    setCollapsed((p) => ({ ...p, [grade]: next }));
    await api.patch("/classes/visibility", { grade: String(grade), visible: !next }).catch(() => {});
    loadClasses();
  };

  const selectClass = (c) => {
    setSelected(c);
    loadStudents(c.id);
  };

  const saveClass = async () => {
    try {
      const payload = {
        name: classDialog.name,
        grade: String(classDialog.grade)
      };

      if (classDialog.mode === "add") {
        await api.post("/classes", payload);
        toast.success("Kelas ditambahkan");
      } else {
        await api.put(`/classes/${classDialog.id}`, payload);
        toast.success("Kelas diperbarui");
      }
      setClassDialog(null);
      loadClasses();
    } catch (e) {
      toast.error(parseErrorMessage(e, "Gagal menyimpan kelas"));
    }
  };

  const deleteClass = async (c) => {
    if (!window.confirm(`Hapus kelas ${c.name}?`)) return;
    try {
      await api.delete(`/classes/${c.id}`);
      toast.success("Kelas dihapus");
      if (selected?.id === c.id) { setSelected(null); setStudents([]); }
      loadClasses();
    } catch (e) {
      toast.error(parseErrorMessage(e, "Gagal menghapus kelas"));
    }
  };

  const saveStudent = async () => {
    const d = studentDialog.data;
    try {
      if (studentDialog.mode === "add") {
        if (studentDialog.source === "registered") {
          if (!studentDialog.picks?.length) { 
            toast.error("Pilih minimal satu siswa"); 
            return; 
          }
          
          // Memindahkan setiap siswa terpilih menggunakan Promise.all & endpoint migrate
          await Promise.all(
            studentDialog.picks.map((studentId) =>
              api.post(`/students/${studentId}/migrate`, { class_id: String(selected.id) })
            )
          );
          
          toast.success(`${studentDialog.picks.length} siswa berhasil dimasukkan ke ${selected.name}`);
        } else {
          await api.post("/students", { ...d, class_id: String(selected.id) });
          toast.success("Siswa ditambahkan");
        }
      } else {
        await api.put(`/students/${d.id}`, { ...d, class_id: String(d.class_id) });
        toast.success("Data siswa diperbarui");
      }
      setStudentDialog(null);
      loadStudents(selected.id);
      loadClasses();
    } catch (e) {
      toast.error(parseErrorMessage(e, "Gagal menyimpan siswa"));
    }
  };

  const deleteStudent = async (s) => {
    if (!window.confirm(`Hapus siswa ${s.name}?`)) return;
    try {
      await api.delete(`/students/${s.id}`);
      toast.success("Siswa dihapus");
      loadStudents(selected.id);
      loadClasses();
    } catch (e) {
      toast.error(parseErrorMessage(e, "Gagal menghapus siswa"));
    }
  };

  const doMigrate = async () => {
    if (!migrateTarget) return;
    try {
      const r = await api.post(`/students/${migrateDialog.id}/migrate`, { class_id: String(migrateTarget) });
      toast.success(`${r.data.name} dipindahkan ke ${r.data.class_name}`);
      setMigrateDialog(null);
      setMigrateTarget("");
      loadStudents(selected.id);
      loadClasses();
    } catch (e) {
      toast.error(parseErrorMessage(e, "Migrasi gagal"));
    }
  };

  const togglePick = (id) => {
    setStudentDialog((p) => ({
      ...p,
      picks: p.picks.includes(id) ? p.picks.filter((x) => x !== id) : [...p.picks, id],
    }));
  };

  const pickList = studentDialog?.mode === "add"
    ? allStudents.filter((s) => {
        if (s.class_id === selected?.id) return false;
        const q = (studentDialog.search || "").toLowerCase();
        return !q || s.name.toLowerCase().includes(q) || s.nisn.includes(q);
      })
    : [];

  return (
    <div className="space-y-8" data-testid="kelas-page">
      {!selected ? (
        <>
          <div className="flex items-end justify-between">
            <div>
              <h1 className="text-3xl font-bold text-[#111827]">Kelas</h1>
              <p className="text-sm text-[#6B7280] mt-1">Kelola struktur kelas dan data siswa</p>
            </div>
            <Button data-testid="add-class-btn" onClick={() => setClassDialog({ mode: "add", grade: 10, name: "" })} className="bg-[#1D4ED8] hover:bg-[#1E40AF]">
              <Plus className="w-4 h-4 mr-2" /> Tambah Kelas
            </Button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {GRADES.map((grade) => {
              const list = classes.filter((c) => String(c.grade) === String(grade));
              const isCollapsed = !!collapsed[grade];
              return (
                <div key={grade} className="bg-white border border-[#E5E7EB] rounded-xl shadow-sm overflow-hidden self-start" data-testid={`grade-section-${grade}`}>
                  <button
                    data-testid={`toggle-grade-${grade}`}
                    onClick={() => toggleGrade(grade)}
                    className="w-full flex items-center justify-between px-5 py-4 hover:bg-[#F9FAFB] transition-colors duration-150"
                  >
                    <span className="font-heading font-semibold text-[#111827]">Kelas {grade}</span>
                    <span className="flex items-center gap-2 text-xs text-[#6B7280]">
                      {list.length} kelas · {isCollapsed ? "Show" : "Hide"}
                      {isCollapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                    </span>
                  </button>
                  {!isCollapsed && (
                    <div className="border-t border-[#E5E7EB]">
                      {list.length === 0 && <p className="px-5 py-4 text-sm text-[#6B7280]">Belum ada kelas.</p>}
                      {list.map((c) => (
                        <div
                          key={c.id}
                          data-testid={`class-item-${c.id}`}
                          className="group flex items-center justify-between px-5 py-3 cursor-pointer border-b border-[#F3F4F6] last:border-0 hover:bg-[#F9FAFB] transition-colors duration-150"
                          onClick={() => selectClass(c)}
                        >
                          <div>
                            <p className="text-sm font-medium text-[#111827]">{c.name}</p>
                            <p className="text-[11px] text-[#6B7280]">{c.student_count} siswa</p>
                          </div>
                          <div className="flex items-center gap-1">
                            <button data-testid={`edit-class-${c.id}`} className="p-1.5 rounded-md hover:bg-white text-[#6B7280] opacity-0 group-hover:opacity-100 transition-opacity duration-150"
                              onClick={(e) => { e.stopPropagation(); setClassDialog({ mode: "edit", id: c.id, name: c.name, grade: c.grade }); }}>
                              <Pencil className="w-3.5 h-3.5" />
                            </button>
                            <button data-testid={`delete-class-${c.id}`} className="p-1.5 rounded-md hover:bg-white text-red-500 opacity-0 group-hover:opacity-100 transition-opacity duration-150"
                              onClick={(e) => { e.stopPropagation(); deleteClass(c); }}>
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                            <ChevronRight className="w-4 h-4 text-[#9CA3AF]" />
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </>
      ) : (
        <>
          <div className="flex items-end justify-between">
            <div>
              <button data-testid="back-to-classes-btn" onClick={() => { setSelected(null); setStudents([]); }}
                className="flex items-center gap-1.5 text-sm text-[#6B7280] hover:text-[#1D4ED8] transition-colors duration-150 mb-2">
                <ArrowLeft className="w-4 h-4" /> Kembali ke Daftar Kelas
              </button>
              <h1 className="text-3xl font-bold text-[#111827]">{selected.name}</h1>
              <p className="text-sm text-[#6B7280] mt-1">Kelas {selected.grade} · {students.length} siswa terdaftar</p>
            </div>
            <Button data-testid="add-student-btn" onClick={async () => {
              try {
                const r = await api.get("/students");
                setAllStudents(r.data);
              } catch (e) {
                toast.error(parseErrorMessage(e, "Gagal mengambil data siswa"));
              }
              setStudentDialog({ mode: "add", source: "registered", picks: [], search: "", data: { ...EMPTY_STUDENT } });
            }} className="bg-[#1D4ED8] hover:bg-[#1E40AF]">
              <UserPlus className="w-4 h-4 mr-2" /> Tambah Siswa
            </Button>
          </div>

          <div className="bg-white border border-[#E5E7EB] rounded-xl shadow-sm" data-testid="student-panel">
            <div className="overflow-x-auto">
              <table className="w-full text-sm" data-testid="student-table">
                <thead>
                  <tr className="text-left text-xs text-[#6B7280] border-b border-[#E5E7EB] bg-[#F9FAFB]">
                    <th className="px-6 py-3 font-medium w-12">No</th>
                    <th className="px-6 py-3 font-medium">NIS/NISN</th>
                    <th className="px-6 py-3 font-medium">Nama</th>
                    <th className="px-6 py-3 font-medium">L/P</th>
                    <th className="px-6 py-3 font-medium">Status</th>
                    <th className="px-6 py-3 font-medium text-right">Aksi</th>
                  </tr>
                </thead>
                <tbody>
                  {students.map((s, i) => (
                    <tr key={s.id} data-testid={`student-row-${s.id}`} className="border-b border-[#F3F4F6] last:border-0 hover:bg-[#F9FAFB] transition-colors duration-100">
                      <td className="px-6 py-3.5 font-mono text-xs text-[#6B7280]">{i + 1}</td>
                      <td className="px-6 py-3.5 font-mono text-xs">{s.nisn}</td>
                      <td className="px-6 py-3.5 font-medium text-[#111827]">{s.name}</td>
                      <td className="px-6 py-3.5 text-[#6B7280]">{s.gender}</td>
                      <td className="px-6 py-3.5">
                        <span className="text-xs px-2 py-1 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200">{s.status}</span>
                      </td>
                      <td className="px-6 py-3.5 text-right">
                        <div className="flex justify-end gap-1">
                          <button data-testid={`migrate-student-${s.id}`} title="Pindah kelas" className="p-2 rounded-lg hover:bg-blue-50 text-[#1D4ED8] transition-colors duration-100"
                            onClick={() => { setMigrateDialog(s); setMigrateTarget(""); }}>
                            <ArrowRightLeft className="w-4 h-4" />
                          </button>
                          <button data-testid={`edit-student-${s.id}`} title="Ubah" className="p-2 rounded-lg hover:bg-gray-100 text-[#6B7280] transition-colors duration-100"
                            onClick={() => setStudentDialog({ mode: "edit", data: { ...s } })}>
                            <Pencil className="w-4 h-4" />
                          </button>
                          <button data-testid={`delete-student-${s.id}`} title="Hapus" className="p-2 rounded-lg hover:bg-red-50 text-red-500 transition-colors duration-100"
                            onClick={() => deleteStudent(s)}>
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                  {students.length === 0 && (
                    <tr><td colSpan={6} className="px-6 py-10 text-center text-sm text-[#6B7280]">Belum ada siswa di kelas ini.</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}

      {/* Dialog Kelas */}
      <Dialog open={!!classDialog} onOpenChange={() => setClassDialog(null)}>
        <DialogContent data-testid="class-dialog">
          <DialogHeader><DialogTitle>{classDialog?.mode === "add" ? "Tambah Kelas" : "Ubah Kelas"}</DialogTitle></DialogHeader>
          <div className="space-y-4 py-2">
            <div>
              <Label>Nama Kelas</Label>
              <Input data-testid="class-name-input" className="mt-1.5" placeholder="cth: 10 IPA-A" value={classDialog?.name || ""}
                onChange={(e) => setClassDialog((p) => ({ ...p, name: e.target.value }))} />
            </div>
            <div>
              <Label>Tingkat</Label>
              <Select value={String(classDialog?.grade || 10)} onValueChange={(v) => setClassDialog((p) => ({ ...p, grade: v }))}>
                <SelectTrigger data-testid="class-grade-select" className="mt-1.5"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {GRADES.map((g) => <SelectItem key={g} value={String(g)}>Kelas {g}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setClassDialog(null)}>Batal</Button>
            <Button data-testid="class-save-btn" onClick={saveClass} className="bg-[#1D4ED8] hover:bg-[#1E40AF]">Simpan</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Dialog Siswa */}
      <Dialog open={!!studentDialog} onOpenChange={() => setStudentDialog(null)}>
        <DialogContent data-testid="student-dialog">
          <DialogHeader><DialogTitle>{studentDialog?.mode === "add" ? `Tambah Siswa · ${selected?.name}` : "Ubah Data Siswa"}</DialogTitle></DialogHeader>
          {studentDialog?.mode === "add" && (
            <div className="grid grid-cols-2 gap-2 p-1 bg-[#F3F4F6] rounded-lg">
              <button data-testid="source-registered-btn"
                onClick={() => setStudentDialog((p) => ({ ...p, source: "registered" }))}
                className={`py-2 text-sm font-medium rounded-md transition-colors duration-150 ${studentDialog.source === "registered" ? "bg-white text-[#1D4ED8] shadow-sm" : "text-[#6B7280]"}`}>
                Dari Siswa Terdaftar
              </button>
              <button data-testid="source-manual-btn"
                onClick={() => setStudentDialog((p) => ({ ...p, source: "manual" }))}
                className={`py-2 text-sm font-medium rounded-md transition-colors duration-150 ${studentDialog.source === "manual" ? "bg-white text-[#1D4ED8] shadow-sm" : "text-[#6B7280]"}`}>
                Input Manual
              </button>
            </div>
          )}
          {studentDialog?.mode === "add" && studentDialog.source === "registered" ? (
            <div className="space-y-3 py-2">
              <div>
                <Label>Cari & Pilih Siswa (bisa banyak sekaligus)</Label>
                <div className="relative mt-1.5">
                  <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-[#9CA3AF]" />
                  <Input data-testid="pick-search-input" className="pl-9" placeholder="Cari nama atau NIS/NISN..."
                    value={studentDialog.search || ""}
                    onChange={(e) => setStudentDialog((p) => ({ ...p, search: e.target.value }))} />
                </div>
              </div>
              <div className="border border-[#E5E7EB] rounded-lg max-h-64 overflow-y-auto divide-y divide-[#F3F4F6]" data-testid="pick-student-list">
                {pickList.length === 0 && <p className="px-4 py-6 text-center text-sm text-[#6B7280]">Tidak ada siswa yang cocok.</p>}
                {pickList.map((s) => {
                  const checked = studentDialog.picks.includes(s.id);
                  return (
                    <label key={s.id} data-testid={`pick-option-${s.id}`}
                      className={`flex items-center gap-3 px-4 py-2.5 cursor-pointer transition-colors duration-100 ${checked ? "bg-blue-50" : "hover:bg-[#F9FAFB]"}`}>
                      <Checkbox checked={checked} onCheckedChange={() => togglePick(s.id)} />
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-[#111827] truncate">{s.name}</p>
                        <p className="text-[11px] font-mono text-[#6B7280]">{s.nisn}</p>
                      </div>
                      <span className={`text-[11px] px-2 py-0.5 rounded-full border shrink-0 ${s.class_name ? "bg-blue-50 text-blue-700 border-blue-200" : "bg-gray-100 text-gray-500 border-gray-200"}`}>
                        {s.class_name || "Belum ada kelas"}
                      </span>
                    </label>
                  );
                })}
              </div>
              <div className="flex items-center justify-between gap-3">
                <p className="text-[11px] text-[#6B7280]">Jika siswa sudah memiliki kelas, siswa akan dipindahkan ke kelas ini.</p>
                <span className="text-xs font-medium text-[#1D4ED8] shrink-0" data-testid="pick-count">{studentDialog.picks.length} dipilih</span>
              </div>
            </div>
          ) : (
            <div className="space-y-4 py-2">
              <div>
                <Label>NIS/NISN</Label>
                <Input data-testid="student-nisn-input" className="mt-1.5" value={studentDialog?.data.nisn || ""}
                  onChange={(e) => setStudentDialog((p) => ({ ...p, data: { ...p.data, nisn: e.target.value } }))} />
              </div>
              <div>
                <Label>Nama Lengkap</Label>
                <Input data-testid="student-name-input" className="mt-1.5" value={studentDialog?.data.name || ""}
                  onChange={(e) => setStudentDialog((p) => ({ ...p, data: { ...p.data, name: e.target.value } }))} />
              </div>
              <div>
                <Label>Jenis Kelamin</Label>
                <Select value={studentDialog?.data.gender || "L"} onValueChange={(v) => setStudentDialog((p) => ({ ...p, data: { ...p.data, gender: v } }))}>
                  <SelectTrigger data-testid="student-gender-select" className="mt-1.5"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="L">Laki-laki</SelectItem>
                    <SelectItem value="P">Perempuan</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setStudentDialog(null)}>Batal</Button>
            <Button data-testid="student-save-btn" onClick={saveStudent} className="bg-[#1D4ED8] hover:bg-[#1E40AF]">Simpan</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Dialog Migrasi */}
      <Dialog open={!!migrateDialog} onOpenChange={() => setMigrateDialog(null)}>
        <DialogContent data-testid="migrate-dialog">
          <DialogHeader><DialogTitle>Migrasi / Perpindahan Kelas</DialogTitle></DialogHeader>
          {migrateDialog && (
            <div className="space-y-4 py-2">
              <div className="bg-[#F9FAFB] border border-[#E5E7EB] rounded-lg p-4">
                <p className="text-sm font-medium text-[#111827]">{migrateDialog.name}</p>
                <p className="text-xs text-[#6B7280] mt-0.5">NIS/NISN {migrateDialog.nisn} · Kelas saat ini: <span className="font-medium text-[#111827]">{migrateDialog.class_name}</span></p>
              </div>
              <div>
                <Label>Pindahkan ke</Label>
                <Select value={migrateTarget} onValueChange={setMigrateTarget}>
                  <SelectTrigger data-testid="migrate-target-select" className="mt-1.5"><SelectValue placeholder="Pilih kelas tujuan" /></SelectTrigger>
                  <SelectContent>
                    {classes.filter((c) => c.id !== migrateDialog.class_id).map((c) => (
                      <SelectItem key={c.id} value={c.id} data-testid={`migrate-option-${c.id}`}>{c.name} (Kelas {c.grade})</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <p className="text-[11px] text-[#6B7280]">Riwayat kelas lama tidak disimpan — hanya kelas aktif siswa yang diperbarui.</p>
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setMigrateDialog(null)}>Batal</Button>
            <Button data-testid="migrate-confirm-btn" onClick={doMigrate} disabled={!migrateTarget} className="bg-[#1D4ED8] hover:bg-[#1E40AF]">Pindahkan</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}