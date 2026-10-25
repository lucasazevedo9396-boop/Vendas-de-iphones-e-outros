"""Pulso iPhone: servidor com autenticação e persistência SQLite ou PostgreSQL."""
import hashlib, hmac, http.cookies, json, os, secrets, sqlite3, time
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path

ROOT = Path(__file__).resolve().parent
from contextlib import contextmanager
DATABASE_URL = os.environ.get('DATABASE_URL', '')
EMPTY = dict(stock=[], sales=[], clients=[], expenses=[])

class PostgresConnection:
    def __init__(self, db): self.db = db
    def execute(self, query, params=()):
        return self.db.execute(query.replace('?', '%s'), params)
    def commit(self): self.db.commit()

@contextmanager
def connect():
    if DATABASE_URL:
        import psycopg
        # Verifica certificado e hostname; não permite conexão remota sem TLS.
        db = psycopg.connect(DATABASE_URL, connect_timeout=15,
            sslmode='verify-full', sslrootcert=os.environ.get('PULSO_DATABASE_CA', '/etc/ssl/certs/ca-certificates.crt'))
        with db: yield PostgresConnection(db)
    else:
        if os.environ.get('RENDER') == 'true':
            raise RuntimeError('Configure DATABASE_URL: SQLite local não é persistente no Render gratuito.')
        db = sqlite3.connect(DB, timeout=10)
        try:
            db.execute('PRAGMA foreign_keys=ON')
            with db: yield db
        finally: db.close()

if not DATABASE_URL:
    DB = Path(os.environ.get('PULSO_DB', str(ROOT / '.data/pulso.sqlite3')))
    DB.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(DB.parent, 0o700)

with connect() as db:
    for query in [
        'CREATE TABLE IF NOT EXISTS account (id INTEGER PRIMARY KEY CHECK(id=1), username TEXT NOT NULL, salt TEXT NOT NULL, password TEXT NOT NULL)',
        'CREATE TABLE IF NOT EXISTS sessions (token TEXT PRIMARY KEY, csrf TEXT NOT NULL, expires DOUBLE PRECISION NOT NULL)',
        'CREATE TABLE IF NOT EXISTS state (id INTEGER PRIMARY KEY CHECK(id=1), value TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 0)',
    ]: db.execute(query)
    db.execute('INSERT INTO state (id,value,revision) VALUES (1,?,0) ON CONFLICT (id) DO NOTHING', (json.dumps(EMPTY),))
if not DATABASE_URL: os.chmod(DB, 0o600)

def password_hash(password, salt):
    return hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()

def validate(data):
    import math, re
    if not isinstance(data, dict) or set(data) != set(EMPTY):
        raise ValueError('Backup deve conter estoque, vendas, clientes e despesas.')
    for key in EMPTY:
        if not isinstance(data[key], list): raise ValueError('Formato inválido: ' + key)
        ids = set()
        for item in data[key]:
            if not isinstance(item, dict) or not isinstance(item.get('id'), str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}',item['id']) or item['id'] in ids:
                raise ValueError('Registro sem identificação ou identificação duplicada.')
            ids.add(item['id'])
            for field in {'stock': ['cost','ask'], 'sales': ['price','cost','fee'], 'expenses':['value'], 'clients':[]}[key]:
                value = item.get(field)
                if isinstance(value, bool) or not isinstance(value, (float,int)) or not math.isfinite(value) or value < 0:
                    raise ValueError('Valor monetário inválido: '+field)
            for value in item.values():
                if isinstance(value, (dict,list)): raise ValueError('Campo inválido.')
    for item in data['clients']:
        if not isinstance(item.get('name'),str) or not item['name'].strip(): raise ValueError('Nome do cliente obrigatório.')
    for item in data['stock']:
        if not item.get('model') or item.get('status') not in ['Disponível','Reservado','Vendido']: raise ValueError('Aparelho inválido.')
        battery=item.get('battery')
        if battery is not None and (not isinstance(battery,(int,float)) or not 0 <= battery <= 100): raise ValueError('Bateria inválida.')
    imeis=[s['imei'].strip() for s in data['stock'] if s.get('imei','').strip()]
    if len(imeis)!=len(set(imeis)): raise ValueError('IMEI já cadastrado.')
    stocks={s['id']:s for s in data['stock']}; clients={c['id'] for c in data['clients']}; sold=set()
    for sale in data['sales']:
        sid=sale.get('stockId')
        if sid not in stocks or sale.get('clientId') not in clients or sid in sold: raise ValueError('Venda duplicada ou referência inválida.')
        sold.add(sid)
        if stocks[sid]['status']!='Vendido': raise ValueError('Aparelho vendido deve ter status Vendido.')
        received=sale.get('received',sale['price'])
        if not isinstance(received,(float,int)) or not 0 <= received <= sale['price']: raise ValueError('Valor recebido inválido.')
    from datetime import date
    for item in data['sales']+data['expenses']:
        try: date.fromisoformat(item['date'])
        except (ValueError,KeyError,TypeError): raise ValueError('Data inválida.')

ATTEMPTS={}
class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass
    def send(self, status, payload, cookie=None, content_type='application/json; charset=utf-8'):
        body = payload if isinstance(payload, bytes) else json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('X-Frame-Options','DENY')
        self.send_header('Referrer-Policy','same-origin')
        if cookie: self.send_header('Set-Cookie',cookie)
        self.end_headers(); self.wfile.write(body)
    def session(self, db):
        try:
            cookie=http.cookies.SimpleCookie(self.headers.get('Cookie',''))
            token=cookie['pulso_session'].value
            return db.execute('SELECT token,csrf FROM sessions WHERE token=? AND expires>?',(hashlib.sha256(token.encode()).hexdigest(),time.time())).fetchone()
        except (KeyError,http.cookies.CookieError): return None
    def do_GET(self):
        path=self.path.split('?')[0]
        if path=='/health': return self.send(200,{'ok':True})
        with connect() as db:
            session=self.session(db)
            if path=='/api/session':
                return self.send(200,dict(authenticated=bool(session),setup=not bool(db.execute('SELECT id FROM account').fetchone()),csrf=session[1] if session else None,setupTokenRequired=bool(os.environ.get('PULSO_SETUP_TOKEN'))))
            if path=='/api/state':
                if not session: return self.send(401,{'error':'Entre na sua conta.'})
                value,revision=db.execute('SELECT value,revision FROM state WHERE id=1').fetchone()
                return self.send(200,{'data':json.loads(value),'revision':revision})
            if path in ['/','/pulso_iphone.html']:
                name='pulso_iphone.html' if session else 'login.html'
                return self.send(200,(ROOT/name).read_bytes(),content_type='text/html; charset=utf-8')
            return self.send(404,{'error':'Não encontrado.'})
    def do_POST(self):
        try:
            origin=self.headers.get('Origin')
            if origin and origin not in ['http://'+self.headers.get('Host',''),'https://'+self.headers.get('Host','')]:
                return self.send(403,{'error':'Origem inválida.'})
            length=int(self.headers.get('Content-Length','0'))
            if length>5_000_000: return self.send(413,{'error':'Arquivo excede 5 MB.'})
            body=json.loads(self.rfile.read(length) or b'{}')
            with connect() as db:
                if self.path in ['/api/setup','/api/login']:
                    ip=self.client_address[0]; attempts=[t for t in ATTEMPTS.get(ip,[]) if t>time.time()-300]
                    ATTEMPTS[ip]=attempts
                    if len(attempts)>=10: return self.send(429,{'error':'Muitas tentativas. Aguarde 5 minutos.'})
                    username=body.get('username','').strip(); password=body.get('password','')
                    if self.path=='/api/setup':
                        expected=os.environ.get('PULSO_SETUP_TOKEN','')
                        if expected and not hmac.compare_digest(body.get('setupToken',''),expected): return self.send(403,{'error':'Código de ativação incorreto.'})
                        if len(password)<10 or len(username)<3: raise ValueError('Use nome com 3 caracteres e senha com pelo menos 10 caracteres.')
                        db.execute('SELECT id FROM state WHERE id=1 FOR UPDATE') if DATABASE_URL else db.execute('BEGIN IMMEDIATE')
                        if db.execute('SELECT id FROM account').fetchone(): return self.send(409,{'error':'Conta já configurada.'})
                        salt=secrets.token_hex(16)
                        db.execute('INSERT INTO account VALUES (1,?,?,?)',(username,salt,password_hash(password,salt)))
                    else:
                        account=db.execute('SELECT username,salt,password FROM account').fetchone()
                        if not account or not hmac.compare_digest(password_hash(password,account[1]),account[2]) or username!=account[0]:
                            attempts.append(time.time()); return self.send(401,{'error':'Usuário ou senha incorretos.'})
                    token=secrets.token_urlsafe(32); csrf=secrets.token_urlsafe(32)
                    db.execute('DELETE FROM sessions WHERE expires<?',(time.time(),))
                    db.execute('INSERT INTO sessions VALUES (?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),csrf,time.time()+43200))
                    db.commit()
                    secure='; Secure' if os.environ.get('PULSO_SECURE_COOKIE')=='1' else ''
                    return self.send(200,{'ok':True},f'pulso_session={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age=43200'+secure)
                session=self.session(db)
                if not session: return self.send(401,{'error':'Sessão expirada. Entre novamente.'})
                if not hmac.compare_digest(self.headers.get('X-CSRF-Token',''),session[1]): return self.send(403,{'error':'Recarregue a página para continuar.'})
                if self.path=='/api/logout':
                    db.execute('DELETE FROM sessions WHERE token=?',(session[0],)); db.commit()
                    return self.send(200,{'ok':True},'pulso_session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0')
                if self.path=='/api/state':
                    validate(body['data'])
                    cur=db.execute('UPDATE state SET value=?, revision=revision+1 WHERE id=1 AND revision=?',(json.dumps(body['data']),body['revision']))
                    if cur.rowcount!=1: return self.send(409,{'error':'Dados alterados em outra aba. A página será atualizada; repita a operação.'})
                    db.commit(); return self.send(200,{'revision':body['revision']+1})
                return self.send(404,{'error':'Não encontrado.'})
        except (ValueError,KeyError,TypeError,AttributeError) as e:
            self.send(400,{'error':str(e) if isinstance(e,ValueError) else 'Dados inválidos.'})
        except Exception:
            self.send(500,{'error':'Não foi possível salvar. Verifique o servidor e tente novamente.'})

if __name__=='__main__':
    host=os.environ.get('PULSO_HOST','127.0.0.1'); port=int(os.environ.get('PORT','8000'))
    print(f'Pulso iniciado em {host}:{port}',flush=True)
    ThreadingHTTPServer((host,port),Handler).serve_forever()
