import sys, unittest, tempfile, subprocess, os, socket, time, json, urllib.request, urllib.error, http.cookiejar
from pathlib import Path
class API(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory()
  with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
  cls.base=f'http://127.0.0.1:{port}'
  cls.server_env={k:v for k,v in os.environ.items() if k not in ['DATABASE_URL','RENDER','PULSO_SETUP_TOKEN']}
  # O servidor temporário usa HTTP local; cookies Secure continuam ativos em produção.
  cls.server_env.update(PORT=str(port),PULSO_DB=cls.tmp.name+'/db.sqlite3',PULSO_SETUP_TOKEN='activation-test-only',PULSO_SECURE_COOKIE='0')
  if os.environ.get('PULSO_TEST_DATABASE_URL'): cls.server_env['DATABASE_URL']=os.environ['PULSO_TEST_DATABASE_URL']
  cls.proc=subprocess.Popen([sys.executable,'server.py'],env=cls.server_env,stdout=subprocess.DEVNULL)
  cls.client=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
  for _ in range(100):
   try:cls.call('/api/session');break
   except OSError:time.sleep(.05)
 @classmethod
 def tearDownClass(cls):cls.proc.terminate();cls.proc.wait();cls.tmp.cleanup()
 @classmethod
 def call(cls,path,data=None,csrf=None,client=None):
  headers={'Content-Type':'application/json'}
  if csrf:headers['X-CSRF-Token']=csrf
  req=urllib.request.Request(cls.base+path,data=json.dumps(data).encode() if data is not None else None,headers=headers)
  try:
   with (client or cls.client).open(req) as r:return r.status,json.load(r)
  except urllib.error.HTTPError as e:return e.code,json.load(e)
 def test_auth_persistence_and_validation(self):
  self.assertEqual(self.call('/api/state')[0],401)
  self.assertEqual(self.call('/api/setup',{'username':'admin','password':'TestPassword123!'})[0],403)
  self.assertEqual(self.call('/api/setup',{'username':'admin','password':'short','setupToken':'activation-test-only'})[0],400)
  self.assertEqual(self.call('/api/setup',{'username':'admin','password':'TestPassword123!','setupToken':'activation-test-only'})[0],200)
  csrf=self.call('/api/session')[1]['csrf']
  state=self.call('/api/state')[1];body={'data':state['data'],'revision':state['revision']}
  self.assertEqual(self.call('/api/state',body)[0],403)
  body['data']={'stock':[{'id':'phone1','model':'iPhone 13','status':'Vendido','cost':2000,'ask':2800}], 'clients':[{'id':'client1','name':'Cliente teste'}], 'sales':[{'id':'sale1','stockId':'phone1','clientId':'client1','date':'2026-10-25','price':2800,'cost':2000,'fee':100,'received':1500}], 'expenses':[{'id':'expense1','date':'2026-10-25','value':50}]}
  self.assertEqual(self.call('/api/state',body,csrf)[0],200)
  self.assertEqual(self.call('/api/state',body,csrf)[0],409)
  body['revision']+=1;body['data']['stock']=[{'id':"bad'code",'cost':1,'ask':2}]
  self.assertEqual(self.call('/api/state',body,csrf)[0],400)
  self.assertEqual(self.call('/api/logout',{},csrf)[0],200)
  self.assertEqual(self.call('/api/state')[0],401)
  self.assertEqual(self.call('/api/login',{'username':'admin','password':'wrong'})[0],401)
  self.assertEqual(self.call('/api/login',{'username':'admin','password':'TestPassword123!'})[0],200)
  self.assertEqual(self.call('/api/state')[1]['revision'],1)
  self.proc.terminate();self.proc.wait()
  type(self).proc=subprocess.Popen([sys.executable,'server.py'],env=self.server_env,stdout=subprocess.DEVNULL)
  for _ in range(100):
   try:
    result=self.call('/api/state')
    if result[0]==200:break
   except OSError:pass
   time.sleep(.05)
  self.assertEqual(result[0],200)
  self.assertEqual(result[1]['revision'],1)
  self.assertEqual(result[1]['data']['sales'][0]['received'],1500)
  self.assertEqual(result[1]['data']['expenses'][0]['value'],50)
  self.assertFalse(self.call('/api/session')[1]['setup'])
if __name__=='__main__':unittest.main()
