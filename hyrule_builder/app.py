"""Single-window Hyrule setup and game builder."""
from __future__ import annotations
import argparse, os, queue, subprocess, sys, threading, traceback
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from . import __version__
from .runtime import HOOKSHOT_TAG, SUPPORTED_LANGUAGES, build_environment, check_arguments, configure_app_data, source_arguments, tools_root

def _run_process(command, cwd, env, emit, check_marker=None):
    process = subprocess.Popen(command,cwd=str(cwd),env=env,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding="utf-8",errors="replace",bufsize=1,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
    marker_seen=False
    assert process.stdout is not None
    for raw in process.stdout:
        line=raw.rstrip("\r\n")
        if line.startswith("@@progress "):
            try: emit("progress",max(0.0,min(1.0,float(line.split(maxsplit=1)[1]))))
            except (ValueError,IndexError): emit("log",line)
        elif line.startswith("@@stage "):
            emit("status",line.split(maxsplit=2)[-1]); emit("log",line)
        elif check_marker and line.startswith(check_marker):
            marker_seen=True; emit("status",line[len(check_marker):].strip() or "Game dump accepted."); emit("log",line)
        elif line.startswith("@@error "):
            emit("error-line",line[8:]); emit("log",line)
        else: emit("log",line)
    return process.wait(),marker_seen

def self_test():
    try:
        import hyrulefast.integration
        from .vendor.hookshot_builder import setup_parts,paths
        assert __version__=="0.5.0-beta.1" and HOOKSHOT_TAG=="v2.0.14"
        assert callable(hyrulefast.integration.patch_hookshot) and callable(setup_parts.install) and callable(paths.base)
        assert "en-US" in SUPPORTED_LANGUAGES
        return 0
    except Exception: return 2

def bootstrap_check():
    log_path=configure_app_data()/"bootstrap-selftest.log"
    lines=[]
    def emit(message):
        lines.append(message); log_path.write_text("\n".join(lines)+"\n",encoding="utf-8")
    try:
        from .vendor.hookshot_builder import setup_parts
        from hyrulefast.integration import patch_hookshot
        emit("Downloading and verifying official Hookshot "+HOOKSHOT_TAG+" build tools.")
        tag,_=setup_parts.install(lambda s:emit(s),lambda f:emit("Download progress: %s"%f),tag=HOOKSHOT_TAG,repair=False,cancel=lambda:False)
        root=tools_root(tag=tag); emit("Applying Hyrule patches to pinned tool source."); patch_hookshot(root)
        python=root/"python"/"python.exe"; make_game=root/"nx2"/"make_game.py"
        if not python.is_file() or not make_game.is_file():raise RuntimeError("Downloaded compiler tools are incomplete.")
        env=build_environment(root,sys.executable)
        emit("Checking the packaged compiler entry point.")
        r=subprocess.run([str(python),"-I",str(make_game),"--help"],cwd=str(root),env=env,capture_output=True,text=True,encoding="utf-8",errors="replace",timeout=60,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
        if r.returncode:raise RuntimeError((r.stderr or r.stdout or "make_game.py --help failed")[-4000:])
        emit("PASS: packages SHA-256 verified, Hyrule patches applied, compiler CLI starts.")
        return 0
    except Exception:
        emit("FAIL:"); emit(traceback.format_exc()); return 3

class HyruleWindow:
    def __init__(self,root,update_folder=None,update_tag=None,repair=False):
        self.root=root; self.events=queue.Queue(); self.cancel_event=threading.Event(); self.busy=False; self.game_folder=Path(update_folder).resolve() if update_folder else None
        self.update_folder=Path(update_folder).resolve() if update_folder else None; self.update_tag=update_tag
        root.title("Hyrule Builder"); root.geometry("820x690"); root.minsize(720,600); root.configure(background="#10151f")
        self._style(); self._build_ui(); root.after(100,self._drain_events)
        if self.update_folder:
            if update_tag and update_tag!=HOOKSHOT_TAG:self.show_incompatible_update()
            else:self.start_build(update=True)
        elif repair:self.start_build(repair=True)

    def _style(self):
        s=ttk.Style()
        try:s.theme_use("clam")
        except tk.TclError:pass
        s.configure("TFrame",background="#10151f"); s.configure("Card.TFrame",background="#192231")
        s.configure("TLabel",background="#10151f",foreground="#e8eef8",font=("Segoe UI",10))
        s.configure("Muted.TLabel",background="#10151f",foreground="#9aaac0",font=("Segoe UI",9))
        s.configure("Card.TLabel",background="#192231",foreground="#e8eef8",font=("Segoe UI",10))
        s.configure("Title.TLabel",background="#10151f",foreground="#f1f6ff",font=("Segoe UI",24,"bold"))
        s.configure("Section.TLabel",background="#192231",foreground="#f1f6ff",font=("Segoe UI",12,"bold"))
        s.configure("TButton",font=("Segoe UI",10),padding=(12,8)); s.configure("Accent.TButton",font=("Segoe UI",10,"bold"),padding=(16,10))
        s.configure("TEntry",padding=7); s.configure("TCombobox",padding=6); s.configure("TCheckbutton",background="#192231",foreground="#dce6f4")

    def _build_ui(self):
        outer=ttk.Frame(self.root,padding=22); outer.pack(fill="both",expand=True)
        header=ttk.Frame(outer); header.pack(fill="x",pady=(0,18))
        ttk.Label(header,text="HYRULE",style="Title.TLabel").pack(anchor="w")
        ttk.Label(header,text="Native compiler setup  •  Hookshot "+HOOKSHOT_TAG+"  •  Hyrule "+__version__,style="Muted.TLabel").pack(anchor="w",pady=(2,0))
        card=ttk.Frame(outer,style="Card.TFrame",padding=16); card.pack(fill="x")
        ttk.Label(card,text="1. Your game dump",style="Section.TLabel").pack(anchor="w",pady=(0,10))
        ttk.Label(card,text="Select a supported .nup file, or choose both extracted romfs and exefs folders.",style="Card.TLabel").pack(anchor="w",pady=(0,8))
        self.nup_var=tk.StringVar(); self.romfs_var=tk.StringVar(); self.exefs_var=tk.StringVar()
        self.out_var=tk.StringVar(value=str(Path.home()/"Games"/"Hyrule")); self.lang_var=tk.StringVar(value="en-US"); self.prepare_var=tk.BooleanVar(value=True)
        self._file_row(card,"NUP file",self.nup_var,self._browse_nup); self._file_row(card,"RomFS folder",self.romfs_var,self._browse_romfs); self._file_row(card,"ExeFS folder",self.exefs_var,self._browse_exefs)
        outcard=ttk.Frame(outer,style="Card.TFrame",padding=16); outcard.pack(fill="x",pady=(14,0))
        ttk.Label(outcard,text="2. Build options",style="Section.TLabel").pack(anchor="w",pady=(0,10))
        self._file_row(outcard,"Install folder",self.out_var,self._browse_output)
        row=ttk.Frame(outcard,style="Card.TFrame"); row.pack(fill="x",pady=(8,0))
        ttk.Label(row,text="Language",style="Card.TLabel").pack(side="left")
        ttk.Combobox(row,textvariable=self.lang_var,values=SUPPORTED_LANGUAGES,state="readonly",width=14).pack(side="left",padx=(10,24))
        ttk.Checkbutton(row,text="Prepare shaders during build (recommended)",variable=self.prepare_var).pack(side="left")
        ttk.Label(outcard,text="First setup downloads the official compiler/tool packages (about 500 MB). Allow about 60 GB of free disk space for the full build.",style="Card.TLabel",wraplength=730).pack(anchor="w",pady=(10,0))
        controls=ttk.Frame(outer); controls.pack(fill="x",pady=(16,10))
        self.build_button=ttk.Button(controls,text="Build Hyrule",style="Accent.TButton",command=self.start_build); self.build_button.pack(side="left")
        self.cancel_button=ttk.Button(controls,text="Cancel",command=self.cancel,state="disabled"); self.cancel_button.pack(side="left",padx=(8,0))
        self.launch_button=ttk.Button(controls,text="Launch game",command=self.launch,state="disabled"); self.launch_button.pack(side="right")
        self.open_button=ttk.Button(controls,text="Open folder",command=self.open_folder,state="disabled"); self.open_button.pack(side="right",padx=(0,8))
        self.status_var=tk.StringVar(value="Ready. Your game files stay on this PC."); ttk.Label(outer,textvariable=self.status_var,style="Muted.TLabel").pack(anchor="w")
        self.progress=ttk.Progressbar(outer,mode="determinate",maximum=100); self.progress.pack(fill="x",pady=(6,10))
        log_frame=ttk.Frame(outer,style="Card.TFrame",padding=10); log_frame.pack(fill="both",expand=True)
        ttk.Label(log_frame,text="Build log",style="Card.TLabel").pack(anchor="w",pady=(0,6))
        self.log=tk.Text(log_frame,height=12,background="#0b1018",foreground="#c7d4e6",insertbackground="#fff",relief="flat",wrap="word",font=("Consolas",9),padx=10,pady=8)
        self.log.pack(fill="both",expand=True); self._append_log("No ROM or game data is included in this application.")
        self._append_log("This is for the supported Switch 2 game dump; a .z64 N64 ROM is not accepted.")

    def _file_row(self,parent,label,var,command):
        row=ttk.Frame(parent,style="Card.TFrame"); row.pack(fill="x",pady=4)
        ttk.Label(row,text=label,style="Card.TLabel",width=16).pack(side="left")
        ttk.Entry(row,textvariable=var).pack(side="left",fill="x",expand=True,padx=(8,8)); ttk.Button(row,text="Browse",command=command).pack(side="right")
    def _browse_nup(self):
        p=filedialog.askopenfilename(title="Choose your supported game dump",filetypes=[("NUP game dump","*.nup"),("All files","*.*")])
        if p:self.nup_var.set(p)
    def _browse_romfs(self):
        p=filedialog.askdirectory(title="Choose the romfs folder")
        if p:self.romfs_var.set(p)
    def _browse_exefs(self):
        p=filedialog.askdirectory(title="Choose the exefs folder")
        if p:self.exefs_var.set(p)
    def _browse_output(self):
        p=filedialog.askdirectory(title="Choose where to build the game")
        if p:self.out_var.set(p)
    def _append_log(self,line):
        self.log.configure(state="normal"); self.log.insert("end",line+"\n"); self.log.see("end"); self.log.configure(state="disabled")
    def _emit(self,kind,value):self.events.put((kind,value))
    def _drain_events(self):
        try:
            while True:
                kind,value=self.events.get_nowait()
                if kind=="log":self._append_log(str(value))
                elif kind=="status":self.status_var.set(str(value))
                elif kind=="progress":self.progress.configure(value=float(value)*100)
                elif kind=="error-line":self.status_var.set(str(value))
                elif kind=="cancel-state":self.cancel_button.configure(state="normal" if value else "disabled")
                elif kind=="done":self._finished(value)
                elif kind=="failed":self._failed(str(value))
        except queue.Empty:pass
        self.root.after(100,self._drain_events)

    def start_build(self,update=False,repair=False):
        if self.busy:return
        if update:source={"update":str(self.update_folder),"prepare":bool(self.prepare_var.get())}
        elif repair:source={"repair":True}
        else:
            nup=self.nup_var.get().strip(); romfs=self.romfs_var.get().strip(); exefs=self.exefs_var.get().strip()
            if nup:
                if not Path(nup).is_file():messagebox.showerror("Hyrule Builder","The selected .nup file does not exist."); return
                source={"nup":nup}
            elif romfs and exefs:
                if not Path(romfs).is_dir() or not Path(exefs).is_dir():messagebox.showerror("Hyrule Builder","Both romfs and exefs paths must be existing folders."); return
                source={"romfs":romfs,"exefs":exefs}
            else:messagebox.showerror("Hyrule Builder","Choose a .nup file or both romfs and exefs folders."); return
            out=self.out_var.get().strip()
            if not out:messagebox.showerror("Hyrule Builder","Choose an output folder."); return
            source.update({"output":str(Path(out).expanduser().resolve()),"language":self.lang_var.get(),"prepare":bool(self.prepare_var.get())})
        self.busy=True; self.cancel_event.clear(); self.build_button.configure(state="disabled"); self.cancel_button.configure(state="normal")
        self.launch_button.configure(state="disabled"); self.open_button.configure(state="disabled"); self.progress.configure(value=0)
        threading.Thread(target=self._worker,args=(source,),daemon=True).start()

    def _worker(self,source):
        try:
            base=configure_app_data()
            from .vendor.hookshot_builder import setup_parts
            from hyrulefast.integration import patch_hookshot
            self._emit("status","Preparing compiler tools…"); self._emit("log","App data: "+str(base))
            tag,_=setup_parts.install(lambda s:self._emit("log",str(s)),lambda f:self._emit("progress",f if f>=0 else 0),tag=HOOKSHOT_TAG,repair=bool(source.get("repair")),cancel=self.cancel_event.is_set)
            self._emit("cancel-state",False)
            if self.cancel_event.is_set(): raise RuntimeError("Operation cancelled during tool download.")
            tool_root=tools_root(base,tag); self._emit("status","Applying Hyrule compiler and worker optimizations…"); patch_hookshot(tool_root)
            for path in (tool_root/"nx2"/"poll.py",tool_root/"gpu"/"vk"/"vk_jobs.cpp",tool_root/"gpu"/"vk"/"vk_jobs.h",tool_root/"gpu"/"vk"/"vk_replay.cpp"):
                if not path.is_file():raise RuntimeError("Hyrule source integration is incomplete: "+str(path))
            python=tool_root/"python"/"python.exe"; make_game=tool_root/"nx2"/"make_game.py"
            if not python.is_file() or not make_game.is_file():raise RuntimeError("Downloaded build toolchain is incomplete.")
            env=build_environment(tool_root,sys.executable)
            if source.get("repair"):
                self._emit("done",{"folder":None,"update":False,"repair":True}); return
            if source.get("update"):
                out=Path(source["update"]); args=["--update",str(out)]
                if not source.get("prepare",True):args.append("--no-prepare-shaders")
                auto_launch=True
            else:
                out=Path(source["output"])
                args=source_arguments(nup=source.get("nup"),romfs=source.get("romfs"),exefs=source.get("exefs"),output=out,language=source.get("language","en-US"),prepare_shaders=source.get("prepare",True))
                check=check_arguments(nup=source.get("nup"),exefs=source.get("exefs"))
                self._emit("status","Checking the game dump…")
                check_result,marker=_run_process([str(python),"-I",str(make_game),*check],tool_root,env,self._emit,check_marker="@@check ok ")
                if check_result!=0 or not marker:raise RuntimeError("This dump was not accepted by Hookshot. Check that it is the supported game version; see the build log.")
                auto_launch=False
            out.mkdir(parents=True,exist_ok=True)
            self._emit("status","Building the native game…"); self._emit("log","Using Hookshot "+HOOKSHOT_TAG+" with Hyrule "+__version__)
            result,_=_run_process([str(python),"-I",str(make_game),*args],tool_root,env,self._emit)
            if result!=0:raise RuntimeError("Native build failed with exit code %d. See the build log above."%result)
            exe=out/"bin"/"hookshot.exe"
            if not exe.is_file():exe=out/"hookshot.exe"
            if not exe.is_file():raise RuntimeError("Build returned success but hookshot.exe was not found in the output folder.")
            self._emit("done",{"folder":str(out),"update":auto_launch,"repair":False})
        except Exception as exc:
            self._emit("failed","Operation cancelled." if self.cancel_event.is_set() else "%s\n\n%s"%(exc,traceback.format_exc()))

    def cancel(self):
        if self.busy and str(self.cancel_button.cget("state")) != "disabled":
            self.cancel_event.set(); self.status_var.set("Cancelling the tool download…")
    def _finished(self,result):
        self.busy=False; self.build_button.configure(state="normal"); self.cancel_button.configure(state="disabled")
        if result.get("repair"):
            self.status_var.set("Toolchain repaired and Hyrule patches verified."); messagebox.showinfo("Hyrule Builder","The build tools were repaired successfully."); return
        self.game_folder=Path(result["folder"]); self.launch_button.configure(state="normal"); self.open_button.configure(state="normal")
        self.status_var.set("Your game is ready."); self._append_log("Build complete: "+str(self.game_folder))
        if result.get("update"):self.launch(); self.root.after(500,self.root.destroy)
        else:messagebox.showinfo("Hyrule Builder","Your native game is ready. Press Launch game to start it.")
    def _failed(self,message):
        self.busy=False; self.build_button.configure(state="normal"); self.cancel_button.configure(state="disabled")
        self.status_var.set("Build did not finish."); self._append_log(message); messagebox.showerror("Hyrule Builder",message[:3000])
    def launch(self):
        if not self.game_folder:return
        exe=self.game_folder/"bin"/"hookshot.exe"
        if not exe.is_file():exe=self.game_folder/"hookshot.exe"
        if not exe.is_file():messagebox.showerror("Hyrule Builder","Could not find hookshot.exe in the game folder."); return
        env=dict(os.environ); env["HOOKSHOT_NO_UPDATE_CHECK"]="1"; subprocess.Popen([str(exe)],cwd=str(self.game_folder),env=env)
        if self.update_folder:self.root.after(300,self.root.destroy)
    def open_folder(self):
        if self.game_folder and self.game_folder.is_dir():os.startfile(str(self.game_folder))
    def show_incompatible_update(self):
        def warn():
            messagebox.showwarning("Hyrule Builder update","A newer Hookshot release is available, but this Hyrule Builder is pinned to "+HOOKSHOT_TAG+". No update was attempted because this version has not been validated with Hyrule. Install a newer Hyrule Builder release when one is available.")
            if self.game_folder:self.launch()
        self.root.after(250,warn)

def main(argv=None):
    parser=argparse.ArgumentParser(add_help=False)
    parser.add_argument("--self-test",action="store_true"); parser.add_argument("--bootstrap-check",action="store_true")
    parser.add_argument("--update"); parser.add_argument("--tag"); parser.add_argument("--launch"); parser.add_argument("--repair",action="store_true")
    args,_=parser.parse_known_args(argv)
    if args.self_test:return self_test()
    if args.bootstrap_check:return bootstrap_check()
    if args.launch:
        folder=Path(args.launch).resolve(); exe=folder/"bin"/"hookshot.exe"
        if not exe.is_file():exe=folder/"hookshot.exe"
        if exe.is_file():
            env=dict(os.environ,HOOKSHOT_NO_UPDATE_CHECK="1"); subprocess.Popen([str(exe)],cwd=str(folder),env=env); return 0
        return 4
    configure_app_data(); root=tk.Tk(); HyruleWindow(root,update_folder=args.update,update_tag=args.tag,repair=args.repair); root.mainloop(); return 0

if __name__=="__main__":raise SystemExit(main())
