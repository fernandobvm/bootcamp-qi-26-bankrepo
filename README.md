# Banco dos entregadores — API

API REST do banco dos entregadores de aplicativos, feita no Bootcamp QI
Tech 2026 por Fernando Mendes, Victor Kazunori e Matheus Reis.

O banco oferece cadastro de cliente com conta, consulta de saldo,
depósito, transferência entre contas (5 grátis por mês, depois 1% com
mínimo de R$ 1,00), pagamento para fora do banco e extrato paginado.
Em cima disso está a **Caixinha do Equilíbrio**, que guarda parte da
renda dos dias bons e devolve nos dias fracos.

Stack: **Python + FastAPI**, **PostgreSQL** e **Docker**.

| Documento | O que tem |
|---|---|
| [`bootcamp-rfc-modelo.md`](bootcamp-rfc-modelo.md) | a RFC principal: garantias, rotas, códigos de erro, modelo de dados e fluxos |
| [`rfc-caixinha.md`](rfc-caixinha.md) | a RFC da Caixinha do Equilíbrio em detalhe |
| [`docs/como-o-projeto-e-organizado.md`](docs/como-o-projeto-e-organizado.md) | as camadas do código e o papel de cada pasta |

---

## 1. Subir a API

Precisa só do **Docker** com o plugin `docker compose`.

```bash
docker compose up --build
```

Sobem dois serviços: `db` (PostgreSQL 16, já com as tabelas do
`database/database.sql`) e `api` (a API na porta 3000). Quando aparecer
`Application startup complete`, confira:

```bash
curl http://localhost:3000/health_check -i     # 204 = está de pé
```

Todas as rotas, menos `/` e `/health_check`, exigem o cabeçalho
`INTERNAL-TOKEN` (padrão: `default_token`). Sem ele a resposta é
`403 EB000002`.

Para desligar: `Ctrl+C` e depois `docker compose down`. Para apagar
também o banco e recriá-lo do zero (necessário sempre que o
`database/database.sql` mudar): `docker compose down -v`.

## 2. Rotas

A tabela completa, com entradas, saídas e códigos de erro de cada rota,
está na seção "Rotas" da RFC.

| Método e rota | O que faz |
|---|---|
| `POST /customers` | cadastra o cliente e a conta dele |
| `GET /customers/{customer_id}` | busca um cliente |
| `GET /accounts/{account_id}` | saldo e status da conta |
| `PATCH /accounts/{account_id}` | muda o status (`ATIVA`, `SUSPENSA`, `ENCERRADA`) |
| `POST /accounts/{account_id}/deposits` | deposita dinheiro vindo de fora |
| `POST /accounts/{account_id}/transfers` | transfere para outra conta do banco, com a tarifa |
| `POST /accounts/{account_id}/payments` | paga para fora do banco |
| `GET /accounts/{account_id}/transactions` | extrato paginado (`limit` de 1 a 100, `page`, `start_date`, `end_date`) |
| `POST/GET/PATCH /accounts/{account_id}/smoothing-box` | ativa, consulta e altera a caixinha |
| `POST/GET /accounts/{account_id}/smoothing-box/closings` | fecha um dia e lista os fechamentos |
| `POST /accounts/{account_id}/smoothing-box/withdrawals` | resgata da caixinha para a conta |

Valores em dinheiro vão e voltam como **texto** com até duas casas
(`"200.00"`), nunca como número. Depósito, transferência, pagamento e
resgate exigem uma `idempotency_key`: reenviar o mesmo pedido com a mesma
chave devolve a resposta original sem mover dinheiro de novo.

Exemplo, do cadastro ao extrato (troque os ids pelos que voltarem):

```bash
TOKEN="INTERNAL-TOKEN: default_token"
JSON="Content-Type: application/json"

curl -X POST http://localhost:3000/customers -H "$TOKEN" -H "$JSON" \
  -d '{"name": "Ana", "nationality": "brasileira", "document_number": "529.982.247-25", "email": "ana@exemplo.com.br", "birth_date": "1995-03-10"}'

curl -X POST http://localhost:3000/accounts/<account_id>/deposits -H "$TOKEN" -H "$JSON" \
  -d '{"value": "500.00", "idempotency_key": "deposito-1"}'

curl -X POST http://localhost:3000/accounts/<account_id>/transfers -H "$TOKEN" -H "$JSON" \
  -d '{"account_id_in": "<outra_account_id>", "value": "200.00", "idempotency_key": "transferencia-1"}'

curl "http://localhost:3000/accounts/<account_id>/transactions?limit=10&page=0" -H "$TOKEN"
```

## 3. Rodar os testes no Linux (Python 3.12)

Os testes são de integração: rodam na sua máquina e conversam com a API
por HTTP e com o banco pela porta 5432. Por isso a API e o banco precisam
estar de pé (seção 1) antes do `pytest`.

**1. Instalar o Python 3.12** (uma vez só)

```bash
python3.12 --version                              # já tem? pule para o passo 2

# Ubuntu 24.04 (o 3.12 é o Python padrão dele)
sudo apt update && sudo apt install -y python3.12 python3.12-venv

# Ubuntu 22.04 ou anterior: o 3.12 vem do PPA deadsnakes
sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo apt update && sudo apt install -y python3.12 python3.12-venv

# Fedora
sudo dnf install -y python3.12
```

**2. Criar o ambiente virtual e instalar as dependências** (uma vez só,
na raiz do projeto)

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

A pasta `.venv` guarda um Python só deste projeto e já está no
`.gitignore`. Em cada terminal novo, ative de novo com
`source .venv/bin/activate`.

**3. Subir a API e o banco** (em outro terminal, ou em segundo plano)

```bash
docker compose up -d --build
docker compose ps        # espere a api aparecer como (healthy)
```

**4. Rodar os testes**

```bash
pytest                                            # a suíte inteira
pytest -v tests/integration/transaction           # só uma pasta
pytest -v tests/integration/transaction/test_transfer.py
pytest -k fee                                     # só os testes com "fee" no nome
```

O resultado esperado é `117 passed`.

Os testes usam por padrão a API em `0.0.0.0:3000`, o token
`default_token` e o banco em
`postgresql+psycopg2://bootcamp:bootcamp@localhost:5432/bootcamp`, os
mesmos padrões do `docker-compose.yml`. Para mudar algum deles, crie um
`.env` na raiz (o `tests/conftest.py` lê esse arquivo sozinho):

```
API_PORT=3001
DB_PORT=5433
DATABASE_URL=postgresql+psycopg2://bootcamp:bootcamp@localhost:5433/bootcamp
INTERNAL_TOKEN=outro_token
```

Os testes criam clientes e contas no mesmo banco que você usa no `curl`.
Para começar com o banco vazio: `docker compose down -v && docker compose up -d`.

### Quando dá errado

| Mensagem | O que fazer |
|---|---|
| `Não consegui falar com a API em http://0.0.0.0:3000` | a API não está de pé: `docker compose up -d` e espere o `(healthy)` |
| `Não consegui falar com o banco em localhost:5432` | o banco não está de pé, ou o `DATABASE_URL` do `.env` aponta para outra porta |
| `port is already allocated` | outra coisa usa a porta 3000 ou 5432: troque `API_PORT`/`DB_PORT` no `.env` (e a porta do `DATABASE_URL` junto) |
| `permission denied ... docker.sock` | rode com `sudo` ou adicione seu usuário ao grupo: `sudo usermod -aG docker $USER` e abra uma sessão nova |
| `relation "..." does not exist` | o `database/database.sql` mudou depois que o banco nasceu: `docker compose down -v` e suba de novo |
| `No module named ...` | o `.venv` não está ativo: `source .venv/bin/activate` |

## 4. Organização do código

```
src/
  app.py          liga as rotas, os middlewares e o tratamento de erro
  resources/      recebe a requisição HTTP e devolve a resposta
  schemas/        o formato do que entra (JSON Schema)
  controllers/    as regras de negócio: tarifa, idempotência, travas, caixinha
  repositories/   as consultas ao banco
  models/         as tabelas, em SQLAlchemy
  dtos/           transforma o objeto do banco no JSON de saída
  errors/         os erros da API, cada um com seu código EB
  middlewares/    token interno, sessão do banco e log de cada requisição
database/
  database.sql    as tabelas, em SQL
tests/
  integration/    testes por rota: customer, account, transaction, smoothing_box
  utils/          clientes HTTP e geradores de dados para os testes
```

A requisição segue sempre o mesmo caminho:
`resource → controller → repository → banco`. O resource não conhece SQL
e o repository não conhece regra de negócio.

## 5. Erros

Todo erro responde no mesmo formato:

```json
{
  "title": "Insufficient balance",
  "description": "The operation needs 202.00, but the account holds 150.00.",
  "translation": "O saldo da conta não cobre a operação.",
  "code": "EB001008",
  "balance": "150.00"
}
```

Os códigos vêm em faixas: `EB000…` são os erros genéricos (formato,
token, rota inexistente, erro inesperado), `EB001…` os do banco e
`EB002…` os da caixinha. A lista completa, com o status HTTP de cada um,
está na seção "Códigos de erro" da RFC.

## 6. Licença

MIT. Veja o arquivo [`LICENSE`](LICENSE).
