"""Bounded, value-free progress events. Never log SQL, requests or secrets."""
from datetime import datetime, timezone
import json
from pathlib import Path
import time

from .storage import atomic_json
from .locking import MESSAGES

LABELS={
    'LOCK_RECOVERED':'Ancien verrou archivé — son processus est terminé',
    'STARTING':'Préparation de l’opération', 'ONLINE_BACKUP':'Inventaire des fichiers et modèles',
    'QUIESCENCE':'Contrôle de disponibilité', 'DATABASE_INVENTORY':'Inventaire des bases',
    'DATABASE_EXPORT':'Sauvegarde de la base', 'FILES_EXPORT':'Compression et chiffrement des fichiers',
    'ENVIRONMENT_EXPORT':'Chiffrement des variables et paramètres', 'DATABASE_RECHECK':'Vérification des schémas source',
    'VERIFYING':'Vérification intégrale des packages', 'RESTORE_PREFLIGHT':'Contrôles avant restauration',
    'WAITING_FOR_TARGET_STOP':'Attente de la fermeture des services du PC cible',
    'STAGING':'Extraction et préparation des fichiers', 'BACKUP_EXISTING':'Sauvegarde de l’existant sur le PC cible',
    'DATABASE_REPLACEMENT':'Restauration des bases', 'DATABASE_VALIDATION':'Validation des bases restaurées',
    'FILE_REPLACEMENT':'Installation des fichiers et modèles', 'USER_ENVIRONMENT':'Restauration des variables utilisateur',
    'FINALIZING':'Vérifications finales', 'RESTORED_PAUSED':'Données restaurées, services laissés arrêtés',
    'BUILDING_PYTHON':'Création de l’environnement Python et installation des dépendances',
    'ROLLBACK':'Retour à l’état précédant la restauration', 'FAILED_ROLLED_BACK':'Échec — état précédent rétabli',
    'FAILED_ROLLBACK_INCOMPLETE':'Échec — retour arrière incomplet, vérification nécessaire',
    'COMPLETE':'Sauvegarde terminée et vérifiée', 'FINISHED':'Opération terminée',
    'FAILED':'Opération en échec', 'CANCELED':'Opération interrompue',
    'RECOVERING':'Récupération de l’état précédent', 'RECOVERED_PAUSED':'État précédent récupéré',
}
EXPORT={'ONLINE_BACKUP':(0,5),'QUIESCENCE':(0,5),'DATABASE_INVENTORY':(5,10),
        'DATABASE_EXPORT':(10,55),'FILES_EXPORT':(55,82),'ENVIRONMENT_EXPORT':(82,85),
        'DATABASE_RECHECK':(85,90),'VERIFYING':(90,99)}
RESTORE={'VERIFYING':(0,12),'RESTORE_PREFLIGHT':(12,18),'STAGING':(18,35),
         'BACKUP_EXISTING':(35,55),'DATABASE_REPLACEMENT':(55,78),'DATABASE_VALIDATION':(78,85),
         'FILE_REPLACEMENT':(85,93),'USER_ENVIRONMENT':(93,95),'FINALIZING':(95,97),
         'RESTORED_PAUSED':(97,97),'BUILDING_PYTHON':(97,99)}
NUMBERS={'completed','total','part_index','parts_total','files_done','files_total','processed_bytes','total_bytes','owner_pid'}
TEXT={'database','package','item','unit','error_code'}
TERMINAL={'COMPLETE','FINISHED','FAILED','CANCELED','FAILED_ROLLED_BACK','FAILED_ROLLBACK_INCOMPLETE','RECOVERED_PAUSED'}


class Progress:
    def __init__(self,folder,operation,*,mirror=None,clock=time.monotonic):
        self.folders=[Path(folder)]+([Path(mirror)] if mirror else [])
        self.operation=operation;self.clock=clock;self.started=clock()
        self.last_write=-100.;self.last_log=-100.;self.state={
            'operation':operation,'started_at':datetime.now(timezone.utc).isoformat(),
            'phase':'STARTING','status':'RUNNING','percent':0.,'percent_is_estimate':True}
        self.update('STARTING')

    def update(self,phase=None,**fields):
        if phase is not None and phase not in LABELS:raise ValueError('Phase de suivi inconnue')
        phase=phase or self.state['phase'];old=self.state
        if phase in TERMINAL and phase==old['phase'] and fields.get('error_code',old.get('error_code'))==old.get('error_code'):return
        context_change=(phase!=old['phase'] or any(k in fields and fields[k]!=old.get(k) for k in ('database','package')))
        if context_change:
            for key in NUMBERS|TEXT:self.state.pop(key,None)
        self.state['phase']=phase
        for key,value in fields.items():
            if key in NUMBERS and (value is None or type(value) in (int,float) and value>=0):self.state[key]=value
            elif key in TEXT and isinstance(value,str):
                if key!='error_code' or value in MESSAGES:self.state[key]=' '.join(value.split())[:180]
        self.state['status']=phase if phase in TERMINAL else 'RUNNING'
        if fields.get('warning') is True:self.state['warning']=True
        ranges=EXPORT if self.operation=='export' else RESTORE if self.operation=='restore' else {'VERIFYING':(0,99),'RESTORE_PREFLIGHT':(90,99)}
        low,high=ranges.get(phase,(self.state['percent'],self.state['percent']))
        fraction=0.
        if self.state.get('total'):
            fraction=min(1.,self.state.get('completed',0)/self.state['total'])
        elif self.state.get('total_bytes'):
            fraction=min(1.,self.state.get('processed_bytes',0)/self.state['total_bytes'])
        elif self.state.get('files_total'):
            fraction=min(1.,self.state.get('files_done',0)/self.state['files_total'])
        if self.state.get('parts_total'):
            fraction=min(1.,(self.state.get('part_index',0)+fraction)/self.state['parts_total'])
        percent=low+(high-low)*fraction
        self.state['percent']=100. if phase in ('COMPLETE','FINISHED','RECOVERED_PAUSED') else min(99.,max(self.state['percent'],percent))
        now=self.clock();force=context_change or phase in TERMINAL or self.last_write<0 or fields.get('checkpoint') is True
        if not force and now-self.last_write<1.:return
        self.state.update(updated_at=datetime.now(timezone.utc).isoformat(),elapsed_seconds=round(now-self.started,1),label=LABELS[phase])
        log=force or now-self.last_log>=15.
        message=LABELS[phase]
        for key in ('database','package','item'):
            if self.state.get(key):message+=' — '+self.state[key]
        if self.state.get('error_code') in MESSAGES:message+=' — '+MESSAGES[self.state['error_code']]
        if self.state.get('owner_pid'):message+=f" — PID {self.state['owner_pid']}"
        if self.state.get('processed_bytes') is not None:
            message+=f" — {self.state['processed_bytes']:,} octets"
        if self.state.get('files_total'):
            what='tables' if self.state.get('unit')=='tables' else 'fichiers'
            message+=f" — {self.state.get('files_done',0):,}/{self.state['files_total']:,} {what}"
        event={**self.state,'message':message}
        for folder in self.folders:
            # The engine owns creation of output/report dirs (exclusive mkdir).
            if not folder.is_dir():continue
            atomic_json(folder/'tracking.json',self.state)
            if log:
                with (folder/'events.jsonl').open('a',encoding='utf-8') as stream:
                    stream.write(json.dumps(event,ensure_ascii=False)+'\n')
        self.last_write=now
        if log:self.last_log=now


def emit(callback,phase=None,**fields):
    if callback:
        try:callback(phase,**fields)
        except OSError:pass  # Telemetry must never prevent an ongoing rollback.


class CountingWriter:
    def __init__(self,stream,callback):self.stream=stream;self.callback=callback;self.count=0
    def write(self,value):
        result=self.stream.write(value);self.count+=len(value)
        emit(self.callback,processed_bytes=self.count,unit='octets compressés')
        return result
    def flush(self):return self.stream.flush()


class ConsoleProgress(Progress):
    """Portable interactive mode prints the same safe, throttled milestones."""
    def __init__(self,*args,**kwargs):
        self.console_phase=None;self.console_time=-100.;super().__init__(*args,**kwargs)
    def update(self,phase=None,**fields):
        super().update(phase,**fields)
        now=self.clock()
        if self.state['phase']!=self.console_phase or now-self.console_time>=15 or fields.get('checkpoint'):
            label=self.state.get('label',LABELS[self.state['phase']])
            context=self.state.get('database') or self.state.get('package')
            count=self.state.get('processed_bytes')
            print(f"[{self.state['percent']:.0f} %] {label}"+(f' — {context}' if context else '')+(f' — {count:,} octets' if count is not None else ''),flush=True)
            self.console_phase=self.state['phase'];self.console_time=now
