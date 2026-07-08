# StructAI Vision

Medição de m² de fachadas prediais a partir de fotos/vídeo/drone, para quantitativo de orçamento de reformas.

**Leia primeiro:** `docs/roadmap.md` (arquitetura, riscos, stack) e `docs/fable5-guia-execucao.md` (como evoluir este código sessão por sessão com o Fable 5).

---

## O que já está implementado

| Sessão | Escopo | Onde |
|---|---|---|
| **0** — Harness de validação | Script standalone: fotos/vídeo + GCP → ODM → área/altura/perímetro | `scripts/validate_measurement.py` |
| **1** — Arquitetura base | FastAPI + PostgreSQL/PostGIS + Redis/Celery + MinIO + NodeODM, tudo em Docker | `infra/docker-compose.yml`, `backend/` |
| **2** — Captura (lado servidor) | Upload de fotos + GCP + notas, com validações | `backend/app/routers/captures.py` |
| **3** — Pipeline de reconstrução | Task Celery: filtro de nitidez → NodeODM → malha → medição → banco, com tratamento de falha | `backend/app/workers/reconstruction.py` |
| **5** (parcial) — Measure Engine v0 | Área de superfície bruta, altura, perímetro | `backend/app/measure/engine.py` |

**Ainda não implementado** (seguir o guia, nesta ordem): app mobile de captura (Sessão 2 cliente), YOLO/SAM2 (4), área líquida (5), quantitativos (6), patologias (7), Digital Twin (8), RAG de orçamento (9), dashboard (10+).

---

## Antes de tudo: Sessão 0 (validação em campo)

**Não construa mais nada antes disto.** O risco do projeto está na precisão da medição, não no código.

```bash
# 1. suba só o NodeODM
docker run -d -p 3000:3000 opendronemap/nodeodm

# 2. instale as dependências do script
pip install pyodm opencv-python-headless "numpy<2" trimesh shapely

# 3. rode com fotos reais de um prédio + GCP medido com trena/laser
python scripts/validate_measurement.py --images ./fotos_predio_A --gcp ./gcp_list.txt

# ou a partir de vídeo (extrai e filtra frames automaticamente)
python scripts/validate_measurement.py --video ./fachada.mp4 --gcp ./gcp_list.txt
```

Compare o resultado com a medição manual em **2-3 prédios diferentes**. Defina com o comercial o erro aceitável (ex.: ±2-5%). Só avance quando bater.

**Sobre o GCP:** sem ele, o modelo sai em escala relativa e o m² não vale nada. As coordenadas não precisam ser GPS reais — distâncias locais medidas com trena, consistentes entre si, funcionam. Formato no cabeçalho do próprio script.

---

## Subindo o sistema completo

```bash
cp .env.example .env          # ajuste JWT_SECRET
docker compose -f infra/docker-compose.yml up --build
```

Serviços: API em `:8000` (docs em `/docs`), MinIO console em `:9001`, NodeODM em `:3000`.

**GPU:** sem GPU NVIDIA a reconstrução é muito mais lenta (risco 2.3 do roadmap). Para usar GPU, troque a imagem para `opendronemap/nodeodm:gpu` e descomente o bloco `deploy` no compose.

## Fluxo da API

```bash
# registrar e obter token
curl -X POST :8000/auth/register -H 'Content-Type: application/json' \
  -d '{"email":"tecnico@structai.com","password":"..."}'

# criar prédio
curl -X POST :8000/buildings -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d '{"name":"Ed. Alfa","address":"..."}'

# enviar captura (dispara a reconstrução assíncrona)
curl -X POST :8000/buildings/1/captures -H "Authorization: Bearer $TOKEN" \
  -F source=mixed -F gcp=@gcp_list.txt \
  -F images=@f1.jpg -F images=@f2.jpg ...   # 30+ fotos, 70-80% sobreposição

# acompanhar:  GET /captures/{id}        (pending → processing → completed|failed)
# resultado:   GET /captures/{id}/measurement
```

## Decisões de arquitetura (não mudar sem motivo)

- **Ferramentas externas são dependência, nunca código copiado**: ODM roda como serviço (NodeODM), bibliotecas via pip. Ver regra de ouro no guia.
- **Reconstrução sempre assíncrona** (Celery) — leva de minutos a horas.
- **Falha explícita**: capture.status = `failed` + mensagem legível; nunca travar em silêncio.
- **Measurement v0 é área bruta** — a líquida (descontando janelas) depende das Sessões 4-5.

## Próximo passo com o Fable 5

Abra o repositório no Claude Code e siga `docs/fable5-guia-execucao.md` a partir da Sessão 2 (app de captura) — os prompts prontos estão lá. Anexe sempre `docs/roadmap.md` como contexto.
