"""Integração: todas as taxas do print, edições e compatibilidade de backups antigos."""
import copy
from decimal import Decimal, ROUND_HALF_UP
import test_api

class RatesAndEdits(test_api.API):
 def test_auth_persistence_and_validation(self):
  self.assertEqual(self.call('/api/rates')[0],401)
  self.assertEqual(self.call('/api/setup',{'username':'admin','password':'TestPassword123!','setupToken':'activation-test-only'})[0],200)
  csrf=self.call('/api/session')[1]['csrf']
  rates=self.call('/api/rates')[1]
  expected={
   'Visa':(1.37,[3.15,5.39,6.12,6.85,7.57,8.28,8.99,9.69,10.38,11.06,11.74,12.40]),
   'Mastercard':(1.37,[3.15,5.39,6.12,6.85,7.57,8.28,8.99,9.69,10.38,11.06,11.74,12.40]),
   'Elo':(2.58,[4.91,6.47,7.20,7.92,8.63,9.33,10.03,10.72,11.41,12.08,12.75,13.41]),
   'Amex':(None,[4.91,6.47,7.20,7.92,8.63,9.33,10.03,10.72,11.41,12.08,12.75,13.41]),
   'Hipercard':(None,[4.91,6.47,7.20,7.92,8.63,9.33,10.03,10.72,11.41,12.08,12.75,13.41]),
   'Link de pagamento':(None,[4.20,6.09,7.01,7.91,8.80,9.67,12.59,13.42,14.25,15.06,15.87,16.66])}
  state=self.call('/api/state')[1]
  data={'stock':[{'id':'phone','model':'iPhone 13','status':'Vendido','cost':2000,'ask':3000},{'id':'phone2','model':'iPhone 14','status':'Disponível','cost':2200,'ask':3300}], 'clients':[{'id':'client','name':'Cliente'}], 'sales':[{'id':'sale','model':'iPhone 13','client':'Cliente','stockId':'phone','clientId':'client','date':'2026-10-25','price':3000,'cost':2000,'fee':77,'received':1000}], 'expenses':[{'id':'expense','date':'2026-10-25','desc':'Frete','value':50}]}
  revision=state['revision']
  def store(payload):
   nonlocal revision
   status,result=self.call('/api/state',{'revision':revision,'data':payload},csrf)
   if status==200:revision=result['revision']
   return status
  self.assertEqual(store(data),200) # backup antigo, taxa manual preservada
  sale=data['sales'][0]
  for brand,(debit,credit) in expected.items():
   self.assertEqual(rates[brand],{'debit':debit,'credit':credit})
   for parts,rate in enumerate(credit,1):
    sale.update(feeMode='automatic',payment='Link de pagamento' if brand=='Link de pagamento' else 'Cartão de crédito',cardBrand=brand,installments=parts,cardAmount=2000.15,fee=float((Decimal('2000.15')*Decimal(str(rate))/100).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)))
    self.assertEqual(store(data),200,(brand,parts))
   sale.update(payment='Cartão de débito',installments=1,fee=round(2000.15*(debit or 0)/100,2))
   self.assertEqual(store(data),400 if debit is None else 200)
  sale.update(payment='Cartão de crédito',cardBrand='Visa',installments=12,cardAmount=3000,fee=372)
  self.assertEqual(store(data),200)
  invalid=copy.deepcopy(data);invalid['sales'][0]['fee']=0
  self.assertEqual(store(invalid),400) # taxa não pode ser adulterada
  invalid=copy.deepcopy(data);invalid['sales'][0]['installments']=13
  self.assertEqual(store(invalid),400)
  # Corrigir dados mantendo os identificadores e recebimentos.
  sale.update(feeMode='manual',fee=123.45,client='Nome corrigido',stockId='phone2',model='iPhone 14',cost=2200)
  data['stock'][0]['status']='Disponível';data['stock'][1]['status']='Vendido'
  data['clients'][0]['name']='Nome corrigido';data['expenses'][0]['value']=80
  self.assertEqual(store(data),200)
  saved=self.call('/api/state')[1]['data']
  self.assertEqual(saved['sales'][0]['received'],1000)
  self.assertEqual(saved['sales'][0]['fee'],123.45)
  self.assertEqual(saved['clients'][0]['name'],'Nome corrigido')
  self.assertEqual(saved['stock'][0]['status'],'Disponível')
  self.assertEqual(saved['expenses'][0]['value'],80)
