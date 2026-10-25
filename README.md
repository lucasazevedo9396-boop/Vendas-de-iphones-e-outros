# Pulso iPhone

Gestão de estoque, vendas, clientes e financeiro em português. Interface baseada no HTML original fornecido pelo usuário, com servidor Python e SQLite. Não exige pacotes externos.

## Iniciar

Com Python 3.12 ou superior:

```sh
cd /workspace/Vendas-de-iphones-e-outros
python3 server.py
```

O servidor escuta em 127.0.0.1:8000. `PORT`, `PULSO_HOST` e `PULSO_DB` podem configurar porta, interface e caminho do banco. No primeiro acesso, crie seu usuário e senha (mínimo 10 caracteres). Não existe senha padrão. A primeira pessoa que acessar um banco novo define a conta: faça isso antes de expor o serviço.

A aplicação deve ser aberta pelo servidor; abrir o HTML diretamente não funciona nesta versão. Para disponibilizar na internet, use hospedagem persistente e proxy HTTPS, configure `PULSO_SECURE_COOKIE=1` e proteja o acesso ao servidor de origem. O servidor incluído é destinado ao desenvolvimento e uso local; publicação pública exige implantação própria.

## Recursos

- Login, logout, senha com hash scrypt, sessão de 12 horas, proteção CSRF e limite de tentativas de login.
- Cadastro individual de aparelhos, bateria, IMEI único, fornecedor, data de entrada e observações; reserva no cadastro e liberação de reservados.
- Venda vinculada ao estoque e cliente, taxa em reais, garantia e observações.
- Valor recebido, saldo a receber e registro de recebimentos parciais.
- Dashboard com filtros, faturamento, lucro estimado, estoque e modelos vendidos.
- Despesas e backup JSON com validação no servidor.
- Controle de revisão para impedir sobrescrita silenciosa por outra aba.

O lucro estimado é venda menos custo, taxa e despesas; não é fluxo de caixa e não inclui tributos não registrados. O gráfico mostra sempre os últimos sete dias, respeitando os filtros. Não há agenda de parcelas com vencimentos, recuperação de senha por e-mail, múltiplos usuários, edição/cancelamento de vendas ou integração WhatsApp.

## Dados e backups

O banco fica em `.data/pulso.sqlite3`, ignorado pelo Git. Faça backup independente do banco e exporte os registros na aba Financeiro. O JSON contém os registros comerciais, sem senha ou sessões. Importar substitui os registros existentes após confirmação. Para migrar o HTML antigo, exporte o backup no navegador antigo e importe na nova versão. Os dados locais antigos não são enviados automaticamente.

## Verificação

```sh
python3 -m unittest discover -s tests -v
```

A suíte usa banco e servidor temporários e verifica login, bloqueio sem sessão, CSRF, validação, conflitos entre revisões e persistência após novo login. O fluxo completo de cadastro, venda, despesas, backup e recebimento parcial também foi exercitado em Chromium durante a implementação.
