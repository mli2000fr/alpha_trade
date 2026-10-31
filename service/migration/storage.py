"""Authenticated streaming packages, split files and safe path handling."""
from contextlib import contextmanager
import base64
import hashlib
import hmac
import io
import json
import os
from pathlib import Path, PurePosixPath
import struct
import re

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

MAGIC=b'ATPKG1\x00'
BLOCK=1024*1024


def canonical(value):
    return json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode('utf-8')


def atomic_json(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_name(path.name+'.'+os.urandom(6).hex()+'.tmp')
    try:
        temporary.write_bytes(canonical(value));os.replace(temporary,path)
    finally:
        temporary.unlink(missing_ok=True)


def sha_file(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(BLOCK),b''):digest.update(block)
    return digest.hexdigest()


def key(password,salt):
    if not isinstance(password,str) or len(password)<12:
        raise ValueError('Le mot de passe de sauvegarde doit contenir au moins 12 caractères')
    return Scrypt(salt=salt,length=32,n=2**15,r=8,p=1).derive(password.encode('utf-8'))


def seal_manifest(payload,password):
    salt=os.urandom(16)
    return dict(payload=payload,salt=base64.b64encode(salt).decode(),
        authentication=hmac.new(key(password,salt),canonical(payload),hashlib.sha256).hexdigest())


def open_manifest(path,password):
    doc=json.loads(Path(path).read_text(encoding='utf-8'))
    salt=base64.b64decode(doc['salt'],validate=True)
    if len(salt)!=16:raise ValueError('Manifest invalide')
    expected=hmac.new(key(password,salt),canonical(doc['payload']),hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected,doc['authentication']):
        raise ValueError('Mot de passe incorrect ou manifeste altéré')
    if doc['payload'].get('protocol')!='alpha-trade-migration-v1':raise ValueError('Format de migration non pris en charge')
    return doc['payload']


def safe_path(root,name):
    path=PurePosixPath(name)
    if (not name or '\\' in name or ':' in name or '\x00' in name or path.is_absolute()
            or any(p in ('..','.') for p in name.split('/'))):
        raise ValueError('Chemin de package non sûr')
    for part in name.split('/'):
        if (not part or part.endswith((' ','.')) or any(c in part for c in '<>"|?*')
                or re.fullmatch(r'(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?',part,re.I)):
            raise ValueError('Nom de fichier Windows non sûr')
    root=Path(root).resolve();target=root.joinpath(*path.parts)
    if not target.resolve().is_relative_to(root):raise ValueError('Chemin hors du répertoire autorisé')
    current=target
    while current!=root:
        if current.is_symlink() or (hasattr(current,'is_junction') and current.is_junction()):
            raise ValueError('Lien/jonction interdit dans un chemin de restauration')
        current=current.parent
    return target


def checked_directory(path):
    """Check the operator's path before resolve hides junction/symlink aliases."""
    raw=Path(path).absolute()
    for item in (raw,*raw.parents):
        if item.is_symlink() or item.is_junction():raise ValueError('Destination lien/jonction interdite')
    return raw.resolve()


class SplitWriter:
    def __init__(self,folder,name,limit):
        self.folder=Path(folder);self.name=name;self.limit=limit
        self.parts=[];self.file=None;self.size=0
    def write(self,data):
        count=len(data)
        while data:
            if self.file is None or self.size==self.limit:
                self.close_part();self.folder.mkdir(parents=True,exist_ok=True)
                path=self.folder/f'{self.name}.part{len(self.parts)+1:04d}'
                self.file=path.open('xb');self.size=0
                self.parts.append(dict(path=path.name))
            block=data[:self.limit-self.size];self.file.write(block)
            self.size+=len(block);data=data[len(block):]
        return count
    def flush(self):
        if self.file:self.file.flush()
    def close_part(self):
        if self.file:
            self.file.close();self.file=None
            path=self.folder/self.parts[-1]['path']
            self.parts[-1].update(size=path.stat().st_size,sha256=sha_file(path))
    def close(self):self.close_part()


class PartsReader(io.RawIOBase):
    def __init__(self,folder,parts):
        self.folder=Path(folder);self.paths=iter(parts);self.file=None
    def readable(self):return True
    def readinto(self,buffer):
        while True:
            if self.file is None:
                part=next(self.paths,None)
                if part is None:return 0
                self.file=safe_path(self.folder,part['path']).open('rb')
            n=self.file.readinto(buffer)
            if n:return n
            self.file.close();self.file=None
    def close(self):
        if self.file:self.file.close()
        super().close()


class EncryptWriter:
    def __init__(self,sink,password,label):
        self.sink=sink;self.header=MAGIC+os.urandom(16)
        self.aes=AESGCM(key(password,self.header[len(MAGIC):]));self.label=label.encode();self.index=0
        sink.write(self.header)
    def record(self,data):
        nonce=os.urandom(12)
        encrypted=self.aes.encrypt(nonce,data,self.header+self.label+struct.pack('>Q',self.index))
        self.sink.write(struct.pack('>I',len(encrypted))+nonce+encrypted);self.index+=1
    def write(self,data):
        for offset in range(0,len(data),BLOCK):self.record(data[offset:offset+BLOCK])
        return len(data)
    def flush(self):self.sink.flush()
    def finish(self):self.record(b'');self.sink.flush()


class DecryptReader(io.RawIOBase):
    def __init__(self,source,password,label):
        self.source=source;self.header=self.exact(len(MAGIC)+16)
        if not self.header.startswith(MAGIC):raise ValueError('Package chiffré invalide')
        self.aes=AESGCM(key(password,self.header[len(MAGIC):]));self.label=label.encode()
        self.index=0;self.buffer=b'';self.finished=False
    def readable(self):return True
    def exact(self,n):
        data=self.source.read(n)
        if len(data)!=n:raise ValueError('Package tronqué')
        return data
    def readinto(self,buffer):
        if not self.buffer and not self.finished:
            size=struct.unpack('>I',self.exact(4))[0]
            if not 16<=size<=BLOCK+16:raise ValueError('Taille de bloc invalide')
            nonce=self.exact(12)
            try:self.buffer=self.aes.decrypt(nonce,self.exact(size),self.header+self.label+struct.pack('>Q',self.index))
            except Exception as exc:raise ValueError('Package altéré ou mot de passe incorrect') from exc
            self.index+=1
            if not self.buffer:
                self.finished=True
                if self.source.read(1):raise ValueError('Données après la fin authentifiée')
        count=min(len(buffer),len(self.buffer));buffer[:count]=self.buffer[:count];self.buffer=self.buffer[count:]
        return count


@contextmanager
def encrypted_output(folder,label,password,limit=2*1024**3):
    sink=SplitWriter(folder,label,limit);encrypted=EncryptWriter(sink,password,label)
    try:
        yield encrypted,sink.parts
        encrypted.finish()
    finally:sink.close()


@contextmanager
def decrypted_input(folder,package,password):
    for part in package['parts']:
        path=safe_path(folder,part['path'])
        if path.stat().st_size!=part['size'] or sha_file(path)!=part['sha256']:
            raise ValueError('Package manquant ou empreinte incorrecte')
    source=io.BufferedReader(PartsReader(folder,package['parts']))
    clear=io.BufferedReader(DecryptReader(source,password,package['label']))
    try:
        yield clear
        # Consumers such as tar/gzip can stop at their own EOF. Still require
        # the authenticated final record and prohibit unnoticed trailing bytes.
        while clear.read(BLOCK):pass
    finally:clear.close();source.close()
