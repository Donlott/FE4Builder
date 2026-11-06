"""Install optional ROM code changes through the normal backup/history path."""
import tkinter as tk
from tkinter import ttk,messagebox
import growth_patch
import promotion_patch
import weapon_skills


def save_patch(app,remove=False,patch_name='growth'):
    module,title,details={
        'growth':(growth_patch,'Display growth rates',['Y toggles effective growth percentages on the normal player unit status screen.']),
        'promotion':(promotion_patch,'Negative promotion stats',['Clamp signed personal + class stats to 0 through 30 before applying normal equipment bonuses.']),
        'weapon_skills':(weapon_skills,'Additional weapon skills',['Equipped weapons can grant Adept, Charge/Accost, Vantage, Luna and Sol. Luna/Sol retain native sword eligibility.'])
    }[patch_name]
    rom=app.rom
    before=bytes(rom.data)
    try:
        updating=patch_name=='growth' and not remove and growth_patch.version(rom)==1
        (module.uninstall if remove else module.install)(rom)
        rom.save_original(('Remove' if remove else 'Update' if updating else 'Install')+' '+title,details)
    except Exception:
        rom.data[:]=before
        raise
    app.refresh_after_history()
    if hasattr(app,'update_history_controls'):app.update_history_controls()
    from item_window import ItemWindow
    for window in getattr(app,'editor_windows',[]):
        if isinstance(window,ItemWindow) and window.winfo_exists() and window.rom is rom and not window.pending():window.populate(window.current)


def open_patch_window(app):
    if not app.rom:
        messagebox.showinfo('Patches','Open a ROM first.',parent=app)
        return
    if not app.settle():return
    window=tk.Toplevel(app)
    window.title('FE4Builder — Patches')
    window.resizable(False,False)
    tabs=ttk.Notebook(window);tabs.pack(fill='both',expand=True)
    frame=ttk.Frame(tabs,padding=22);tabs.add(frame,text='Growth rates')
    ttk.Label(frame,text='Display growth rates',font=('Segoe UI',15,'bold')).pack(anchor='w')
    ttk.Label(frame,text='Press SNES Y on a player unit’s normal status screen to show effective\n'
              'growth percentages. Press Y again to return to stats. HP growth appears\n'
              'in the HP field; the other seven growths appear below “Growths %”.\n\n'
              'Uses the game’s growth calculations, including holy blood and inherited\n'
              'growths. Enemy records do not have individual player growths.\n\n'
              'Supports the 8 MiB Project Naga beta 7 ROM profile. Installation checks\n'
              'the required game code and available storage; it does not expand the ROM.\n'
              'Writes to the opened ROM with an automatic backup and undo history.',
              justify='left').pack(anchor='w',pady=14)
    status=tk.StringVar();ttk.Label(frame,textvariable=status).pack(anchor='w',pady=8)
    buttons=ttk.Frame(frame);buttons.pack(fill='x')
    def refresh():
        version=growth_patch.version(app.rom)
        active=version!=0
        status.set('Installed — update available (fixes boosted-stat display)' if version==1 else 'Installed' if active else 'Not installed')
        install.config(text='Update: Display growth rates' if version==1 else 'Install: Display growth rates',
                       state='disabled' if version==2 else 'normal')
        remove.config(state='normal' if active else 'disabled')
    def change(removing=False):
        if not app.settle():return
        try:save_patch(app,removing)
        except Exception as exc:messagebox.showerror('Patch not saved',str(exc),parent=window)
        refresh()
    install=ttk.Button(buttons,text='Install: Display growth rates',command=change);install.pack(side='left')
    remove=ttk.Button(buttons,text='Remove patch',command=lambda:change(True));remove.pack(side='left',padx=8)
    ttk.Button(buttons,text='Close',command=window.destroy).pack(side='right')
    promotion=ttk.Frame(tabs,padding=22);tabs.add(promotion,text='Negative promotion stats')
    ttk.Label(promotion,text='Fix negative stats after promotion',font=('Segoe UI',15,'bold')).pack(anchor='w')
    ttk.Label(promotion,text='Prevents negative stat totals from turning into 30 when a\n'
              'promotion changes to a class with lower bases.\n\n'
              'Class base + signed personal stat is limited to 0 through 30. A total below\n'
              'zero becomes 0. Promotions can still lower a stat when the new\n'
              'class has a lower base; normal equipment bonuses are applied afterward.\n\n'
              'Preserves personal stats, skill effects and the save/load patch.\n'
              'Supports the verified 8 MiB FE4 / Project Naga layout, with or\n'
              'without a copier header. Installation checks all six stat routines\n'
              'and free helper space before writing, with backup and undo history.',
              justify='left').pack(anchor='w',pady=14)
    promotion_status=tk.StringVar();ttk.Label(promotion,textvariable=promotion_status).pack(anchor='w',pady=8)
    promotion_buttons=ttk.Frame(promotion);promotion_buttons.pack(fill='x')
    def refresh_promotion():
        active=promotion_patch.installed(app.rom)
        promotion_status.set('Installed' if active else 'Not installed')
        promotion_install.config(state='disabled' if active else 'normal')
        promotion_remove.config(state='normal' if active else 'disabled')
    def change_promotion(removing=False):
        if not app.settle():return
        try:save_patch(app,removing,patch_name='promotion')
        except Exception as exc:messagebox.showerror('Patch not saved',str(exc),parent=window)
        refresh_promotion()
    promotion_install=ttk.Button(promotion_buttons,text='Install: Negative promotion stats',command=change_promotion);promotion_install.pack(side='left')
    promotion_remove=ttk.Button(promotion_buttons,text='Remove patch',command=lambda:change_promotion(True));promotion_remove.pack(side='left',padx=8)
    ttk.Button(promotion_buttons,text='Close',command=window.destroy).pack(side='right')
    skills=ttk.Frame(tabs,padding=22);tabs.add(skills,text='Additional weapon skills')
    ttk.Label(skills,text='Additional weapon skills',font=('Segoe UI',15,'bold')).pack(anchor='w')
    ttk.Label(skills,text='Enables weapon-granted Adept, Charge/Accost, Vantage, Luna and Sol.\n'
              'Assign them in Item Editor after installing. Skills apply while the\n'
              'weapon is equipped; carried weapons do not grant these effects.\n\n'
              'Luna and Sol keep the native sword-only requirement and proc rules.\n'
              'Existing Critical, Pursuit, Renewal and Paragon flags stay unchanged.\n\n'
              'Supports the 8 MiB Project Naga-compatible layout, including copier\n'
              'headers. Checks game code and free storage before writing.\n'
              'Reserves 2,048 ROM bytes; saves and SRAM size stay unchanged.\n'
              'Removal requires clearing the extra skill assignments first.\n'
              'Writes use automatic backups and undo/redo.',justify='left').pack(anchor='w',pady=14)
    skill_status=tk.StringVar();ttk.Label(skills,textvariable=skill_status,wraplength=560).pack(anchor='w',pady=8)
    skill_buttons=ttk.Frame(skills);skill_buttons.pack(fill='x')
    def refresh_skills():
        try:
            model=weapon_skills.WeaponSkills(app.rom);active=model.installed
            skill_status.set(f'Installed — {sum(bool(v) for v in model.flags)} item types assigned extra skills.' if active else 'Not installed')
            skill_install.configure(state='disabled' if active else 'normal');skill_remove.configure(state='normal' if active else 'disabled')
        except ValueError as error:
            skill_status.set(str(error));skill_install.configure(state='disabled');skill_remove.configure(state='disabled')
    def change_skills(removing=False):
        if not app.settle():return
        try:save_patch(app,removing,patch_name='weapon_skills')
        except Exception as error:messagebox.showerror('Patch not saved',str(error),parent=window)
        refresh_skills()
    skill_install=ttk.Button(skill_buttons,text='Install: Additional weapon skills',command=change_skills);skill_install.pack(side='left')
    skill_remove=ttk.Button(skill_buttons,text='Remove patch',command=lambda:change_skills(True));skill_remove.pack(side='left',padx=8)
    ttk.Button(skill_buttons,text='Close',command=window.destroy).pack(side='right')
    window.bind('<FocusIn>',lambda event:(refresh(),refresh_promotion(),refresh_skills()))
    refresh()
    refresh_promotion()
    refresh_skills()
    return window
