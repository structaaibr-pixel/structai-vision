# StructAI Vision — ROADMAP de Desenvolvimento

**Documento-mestre para continuar o desenvolvimento com o Fable 5 (Claude Code).**
Coloque este arquivo na raiz do repositório e anexe-o como contexto em **toda** sessão de desenvolvimento. Ele descreve o que já existe no código, as convenções que devem ser mantidas e a fila exata do que falta construir.

**Última atualização:** julho de 2026 (Etapa 1 concluída)

---

## 1. Mapa de documentos do repositório

| Arquivo | Papel |
|---|---|
| `docs/roadmap.md` | Visão, arquitetura, riscos técnicos e stack — **o porquê** |
| `docs/fable5-guia-execucao.md` | Método de trabalho com o Fable 5, sessão por sessão — **o como** |
| `ROADMAP.md` (este) | Estado atual do código + fila de execução — **o que fazer agora** |

---

## 2. Status geral

| Etapa | Escopo | Sessão (guia) | Status |
|---|---|---|---|
| — | Harness de validação (script standalone) | 0 | ✅ implementado |
| — | Infra: FastAPI + PostGIS + Celery + MinIO + NodeODM | 1 | ✅ implementado |
| — | API de captura (upload fotos + GCP + notas) | 2 (servidor) | ✅ implementado |
| — | Pipeline assíncrono de reconstrução | 3 | ✅ implementado |
| — | Measure Engine v0 (área bruta, altura, perímetro) | 5 (parcial) | ✅ implementado |
| **0-A** | **Calibração com datasets públicos (GCPs topográficos)** | **0** | 🔧 harness pronto (`scripts/calibrate.py`) — **rodar e commitar o relatório** |
| **0-B** | **Validação de campo (2-3 prédios reais, trena/laser)** | **0** | ⏳ contínua — não bloqueia dev; **obrigatória antes de uso comercial dos números** |
| 1 | Endurecimento da base (Alembic, CI, streaming, vídeo) | — | ✅ implementado |
| 2 | App Flutter de captura + áudio/Whisper | 2 (cliente) | 🔜 pendente |
| 3 | Segmentação (YOLO-World + SAM2) | 4 | 🔜 pendente |
| 4 | Área líquida (Measure Engine v1) | 5 | 🔜 pendente |
| 5 | Quantitativos configuráveis | 6 | 🔜 pendente |
| 6 | Patologias (ABECIS) | 7 | 🔜 pendente |
| 7 | Digital Twin (Open3D + CloudCompare M3C2) | 8 | 🔜 pendente |
| 8 | RAG de orçamento (Qdrant) | 9 | 🔜 pendente |
| 9 | Dashboard web + relatórios PDF | 10 | 🔜 pendente |
| 10 | Inteligência comercial + IFC + API pública | 11-12 | 🔜 pendente |

> Ao concluir uma etapa, atualize esta tabela no mesmo commit.

---

## 3. Estado atual do código

### 3.1 Estrutura

```
structai-vision/
├── ROADMAP.md                      ← este arquivo
├── README.md                       ← como rodar (docker compose) e fluxo da API
├── .env.example                    ← todas as variáveis de ambiente
├── .github/workflows/ci.yml        ← CI: ruff + pytest a cada push/PR
├── docs/
│   ├── roadmap.md
│   ├── fable5-guia-execucao.md
│   ├── calibracao.md               ← metodologia do gate (Fases A/B) + decisão
│   └── calibracao/relatorios/      ← relatórios de calibração (commitados)
├── scripts/
│   ├── validate_measurement.py     ← Sessão 0: fotos/vídeo + GCP → ODM → medidas
│   ├── calibrate.py                ← Gate 0-A/0-B: datasets públicos e de campo → veredito
│   └── calibration_datasets.json   ← registro dos datasets (baixados em runtime)
├── infra/
│   └── docker-compose.yml          ← db, redis, minio, nodeodm, backend, worker
└── backend/
    ├── Dockerfile                  ← python:3.11-slim
    ├── requirements.txt
    ├── requirements-dev.txt        ← ruff + pytest + httpx (CI/dev, fora da imagem)
    ├── pyproject.toml              ← configuração do ruff e do pytest
    ├── alembic.ini
    ├── alembic/                    ← migrações de schema (env.py lê DATABASE_URL)
    │   └── versions/               ← 0001 schema inicial, 0002 has_video
    ├── app/
    │   ├── main.py                 ← FastAPI; lifespan roda as migrações + bucket
    │   ├── config.py               ← pydantic-settings, lê .env
    │   ├── database.py             ← SQLAlchemy 2.0, SessionLocal, get_db
    │   ├── migrations.py           ← `alembic upgrade head` programático
    │   ├── models.py               ← User, Building, Capture, Measurement
    │   ├── schemas.py              ← Pydantic (from_attributes)
    │   ├── auth.py                 ← JWT HS256 + bcrypt, get_current_user
    │   ├── storage.py              ← MinIO: put_bytes, put_stream, put_file, download_to, list_keys
    │   ├── preprocess.py           ← nitidez + extração de frames de vídeo (compartilhado)
    │   ├── measure/engine.py       ← measure_mesh(path) → dict
    │   ├── routers/
    │   │   ├── auth.py             ← POST /auth/register, POST /auth/token
    │   │   ├── buildings.py        ← POST/GET /buildings + get_owned_building()
    │   │   ├── captures.py         ← POST /buildings/{id}/captures (fotos e/ou vídeo), GET /captures/{id}
    │   │   └── measurements.py     ← GET /captures/{id}/measurement
    │   └── workers/
    │       ├── celery_app.py       ← Celery("structai"), broker/backend = Redis
    │       └── reconstruction.py   ← task "reconstruction.run"
    └── tests/                      ← health, migrações, preprocess, API de capturas
```

### 3.2 Modelos de dados (fonte: `backend/app/models.py`)

- **User**: id, email (único), hashed_password
- **Building**: id, owner_id → User, name, address
- **Capture**: id, building_id → Building, `source` (phone|drone|mixed), `status` (pending|processing|completed|failed), image_count, has_gcp, has_video, `notes` (reservado p/ transcrição Whisper), `error` (mensagem legível quando falha)
- **Measurement**: capture_id (único) → Capture, surface_area_m2, height_m, footprint_perimeter_m, mesh_key, pointcloud_key, `raw` (JSON com metadados: vértices, borradas removidas, frames de vídeo, gcp_used)

**Schema só muda via Alembic** (`backend/alembic/versions/`). Banco de dev criado antes do Alembic (via create_all): rode `alembic stamp 0001` uma vez dentro do container do backend e siga com `alembic upgrade head`.

### 3.3 Pipeline de reconstrução (fonte: `workers/reconstruction.py`)

```
POST /buildings/{id}/captures (retorna 202) — fotos e/ou vídeo, upload em streaming
  → imagens salvas no MinIO em   captures/{id}/images/{NNNN}_{nome}
  → vídeo (se enviado) em        captures/{id}/video/{nome}
  → GCP (se enviado) em          captures/{id}/gcp_list.txt
  → run_reconstruction.delay(capture_id)

Task Celery "reconstruction.run":
  1. status = processing
  2. baixa imagens do MinIO; se houver vídeo, extrai 1 a cada 15 frames
     (app/preprocess.py) para o mesmo diretório
  3. filtro de nitidez (Laplaciano ≥ 100; mínimo 20 imagens úteis)
  4. envia ao NodeODM via pyodm — opções: feature/pc-quality = ODM_QUALITY,
     mesh-octree-depth 11, dsm=False, skip-orthophoto=True
  5. localiza malha: odm_texturing/odm_textured_model_geo.obj
     (fallback: odm_meshing/odm_mesh.ply)
  6. measure_mesh() → grava Measurement; artefatos em captures/{id}/results/
  7. status = completed  |  em exceção: status = failed + capture.error legível
```

### 3.4 Convenções de chave no MinIO

Todo objeto vive sob o namespace da captura: `captures/{capture_id}/images/…`, `captures/{capture_id}/video/…`, `captures/{capture_id}/gcp_list.txt`, `captures/{capture_id}/results/…`. Novas features seguem o mesmo padrão (ex.: `captures/{id}/detections/…`, `captures/{id}/audio/…`, `buildings/{id}/reports/…`).

---

## 4. Convenções obrigatórias (o Fable 5 DEVE seguir)

1. **Ferramenta externa é dependência, nunca código copiado.** Biblioteca → `requirements.txt`; aplicação pesada (ODM, CloudCompare, Qdrant) → serviço no `docker-compose.yml`. Jamais vendorizar código-fonte de terceiros no repositório.
2. **Trabalho pesado é sempre task Celery** — endpoints respondem 202 e o cliente consulta status. Nunca reconstrução/inferência síncrona em request HTTP.
3. **Falha explícita**: `status = failed` + mensagem legível em `capture.error` (pt-BR). Nunca travar em silêncio.
4. **Identificadores de código em inglês; mensagens de erro e docs em pt-BR** (padrão já estabelecido).
5. **Mudança de schema só via Alembic** (em vigor desde a Etapa 1 — nunca mais editar tabela na mão).
6. **Todo endpoint/task novo nasce com teste** em `backend/tests/`.
7. **Precisão acima de conveniência**: qualquer número em m² exposto ao usuário precisa ter sido validado contra medição real pelo menos uma vez (ver Gate de medição, seção 6).

---

## 5. Débitos técnicos conhecidos

- **D1** — ✅ quitado (Etapa 1): Alembic configurado; `main.py` usa `lifespan` que roda `alembic upgrade head` no startup.
- **D2** — ✅ quitado (Etapa 1): upload em streaming por chunks (`storage.put_stream`, multipart de 10 MiB), sem carregar o arquivo em memória.
- **D3** — ✅ quitado (Etapa 1): `POST /buildings/{id}/captures` aceita `video`; a task extrai 1 a cada 15 frames via `app/preprocess.py` (lógica compartilhada com o filtro de nitidez).
- **D4** — ✅ quitado (Etapa 1): GitHub Actions (`.github/workflows/ci.yml`) roda ruff + pytest; testes não dependem de infra externa.
- **D5** — Sem paginação nas listagens; sem refresh token. Aceitável por ora, registrar.
- **D6** — Worker com `--concurrency=1` (ODM satura a máquina). Escalar depois com múltiplos workers/nós NodeODM.

---

## 6. Gate de medição — em duas fases (decisão de jul/2026, ver `docs/calibracao.md`)

**Fase A — calibração com datasets públicos (destrava o desenvolvimento).** Rodar `scripts/calibrate.py --dataset copr` (e depois `bellus`) com NodeODM de pé: datasets públicos com GCPs topográficos medidos em campo por terceiros validam o pipeline e a escala métrica (RMS 3D dos resíduos de GCP ≤ 0,05 m). Relatórios em `docs/calibracao/relatorios/` — commitá-los. **Com a Fase A aprovada, as Etapas 3+ podem ser desenvolvidas.**

**Fase B — validação de campo (contínua, obrigatória antes de uso comercial).** O mesmo harness aceita dados próprios: `scripts/calibrate.py --name predio_x --images … --gcp … --truth truth.json` com medidas manuais de trena/laser. Definir com o comercial o erro aceitável (ex.: ±2-5%). Cada obra medida vira ponto de calibração — é essa série que comprova a margem de erro real. Se não bater, o problema está no protocolo de captura/calibração — voltar ao `docs/roadmap.md`, seção 2. **As etapas de precisão (4, 6, 7) só recebem ✅ com comparação de campo (Fase B), e nenhum número de m² vai para cliente sem ela.**

---

## 7. Fila de execução

Regras: **uma etapa por sessão** do Fable 5; anexar este arquivo + `docs/roadmap.md` como contexto; revisar o diff e rodar os testes antes de fazer commit; atualizar a tabela da seção 2.

---

### Etapa 1 — Endurecimento da base — ✅ CONCLUÍDA

**Objetivo:** quitar os débitos D1-D4 antes de empilhar features.
**Entregue:** Alembic (migrações 0001/0002) + lifespan; upload em streaming; vídeo no POST de capturas com extração de frames no servidor (`app/preprocess.py`); CI com ruff + pytest; 16 testes em `backend/tests/`.

---

### Etapa 2 — App Flutter de captura (+ áudio com Whisper)

**Objetivo:** o cliente da Sessão 2 do guia — captura guiada em campo.
**Toca em:** `app/` (novo, Flutter), `backend/app/routers/captures.py`, `backend/requirements.txt` (+`openai-whisper`), novo task `workers/transcription.py`.

**Prompt:**
> Crie o app Flutter em app/ consumindo a API descrita no README: login (POST /auth/token), lista/criação de prédios, e o fluxo de captura: câmera com contador de fotos e alerta de sobreposição, importação de fotos de drone da galeria, fluxo guiado de GCP (usuário marca pontos na foto e digita a distância real medida — gerar o gcp_list.txt no formato do cabeçalho de scripts/validate_measurement.py), gravação de áudio de observações, envio multipart ao POST /buildings/{id}/captures e tela de acompanhamento de status com o erro legível quando status=failed. No backend, aceite `audio: UploadFile | None` no mesmo POST, salve em captures/{id}/audio/ e crie a task Celery "transcription.run" (openai-whisper, modelo small, CPU) que preenche capture.notes com a transcrição.

**Aceite:** captura completa feita pelo celular chega ao backend, reconstrói e devolve a medição; áudio vira texto em `notes`.

---

### Etapa 3 — Segmentação (YOLO-World + SAM2) — *Sessão 4 do guia*

**Objetivo:** detectar janelas, portas, sacadas e ar-condicionado nas imagens e associá-las à captura.
**Toca em:** novo `workers/segmentation.py`, novo modelo `DetectedElement`, migração Alembic, `requirements.txt` (+`ultralytics`; SAM2 conforme instruções de instalação do repositório oficial), novo endpoint `GET /captures/{id}/elements`.

**Nota técnica importante:** YOLO pré-treinado em COCO **não tem classe "janela"**. Começar com detecção de vocabulário aberto (YOLO-World, disponível via ultralytics, com prompts "window", "door", "balcony", "air conditioner") e validar a qualidade nas suas próprias fotos; fine-tune próprio só se o vocabulário aberto não bastar.

**Prompt:**
> Adicione a etapa de segmentação: crie o modelo DetectedElement (id, capture_id FK, source_image_key, class_name, confidence, bbox JSON, mask_key nullable) com migração Alembic; crie a task Celery "segmentation.run" que roda YOLO-World (ultralytics) com as classes window/door/balcony/air_conditioner sobre as imagens nítidas da captura e SAM2 para gerar a máscara de fachada, salvando máscaras em captures/{id}/detections/; encadeie-a ao final de reconstruction.run via Celery chain; exponha GET /captures/{id}/elements. Modelos de peso baixados em runtime para um volume, nunca commitados no repo.

**Aceite:** captura processada lista elementos detectados com confiança e classe; máscaras visíveis no MinIO.

---

### Etapa 4 — Área líquida (Measure Engine v1) — *Sessão 5 do guia*

**Objetivo:** a medida que o orçamento realmente usa: fachada **menos** aberturas.
**Toca em:** `measure/engine.py`, `models.py` (Measurement ganha `openings_area_m2` e `net_area_m2`, nullable, via Alembic), `workers/` (integração).

**Atenção:** esta é a etapa tecnicamente mais difícil da fila. Abordagem sugerida: extrair os planos de fachada da malha (RANSAC com Open3D ou facets do trimesh), projetar as detecções da Etapa 3 nos planos usando as poses de câmera que o ODM exporta (`odm_report`/`opensfm/reconstruction.json` nos assets), calcular a área dos polígonos projetados e subtrair. Validar contra medição manual de 2-3 janelas reais antes de dar por pronta.

**Prompt:**
> Evolua o Measure Engine para v1: usando os assets do ODM já baixados na task de reconstrução, extraia os planos principais de fachada da malha, projete as DetectedElement (bbox/máscara) de cada plano usando as poses de câmera do ODM, calcule openings_area_m2 e net_area_m2 = surface_area_m2 − openings_area_m2, persista nos novos campos de Measurement (migração Alembic) e devolva-os no GET /captures/{id}/measurement. Registre no raw quais detecções foram usadas e descartadas.

**Aceite:** erro da área de aberturas < limite combinado, medido contra janela real de prédio de teste.

---

### Etapa 5 — Quantitativos configuráveis — *Sessão 6 do guia*

**Objetivo:** converter área líquida em itens de orçamento, com regras editáveis (variam por serviço), nunca fixas no código.
**Toca em:** novo modelo `ServiceRule` + `Quantitative`, migração, novo router `quantitatives.py`.

**Prompt:**
> Crie o modelo ServiceRule (service_type: pintura|textura|impermeabilizacao|pastilha|rejunte|junta|rodape, params JSON — ex.: perdas %, demãos, rendimento) editável via CRUD autenticado, e o endpoint POST /captures/{id}/quantitatives que aplica as regras ativas sobre a Measurement (net_area_m2 quando existir, senão surface_area_m2 com aviso) e persiste/retorna a lista de itens com quantidade e unidade (m² ou m linear). Testes cobrindo pelo menos pintura e rejunte.

**Aceite:** mudar uma regra no banco muda o quantitativo sem deploy.

---

### Etapa 6 — Patologias (ABECIS) — *Sessão 7 do guia*

**Objetivo:** fissuras/infiltrações detectadas nos close-ups, com localização e severidade.
**Toca em:** novo `workers/pathology.py`, modelo `Pathology`, migração, endpoint `GET /captures/{id}/pathologies`.

**Ordem certa:** antes de codar, **validar o ABECIS manualmente** nas suas próprias fotos de close-up (ele foi testado com imagens de drone e celular). Se a qualidade servir, integrar; se não, treinar sobre o dataset omnicrack30k é o plano B — decisão registrada aqui.

**Prompt:**
> Integre a detecção de patologias: task Celery "pathology.run" disparada após a segmentação, rodando [ABECIS | modelo próprio conforme decisão acima] sobre as imagens close-up da captura; modelo Pathology (capture_id, type, severity, affected_area_m2 nullable, source_image_key, geometry JSON); resultados em captures/{id}/pathologies/; endpoint de listagem. Severidade e tipo em enum pt-BR (fissura, trinca, infiltracao, eflorescencia, desplacamento…).

**Aceite:** foto com fissura conhecida gera Pathology com localização correta na imagem.

---

### Etapa 7 — Digital Twin (comparação entre inspeções) — *Sessão 8 do guia*

**Objetivo:** dado o mesmo prédio em duas datas, apontar o que mudou.
**Toca em:** novo `workers/change_detection.py`, modelo `ChangeReport`, endpoint `POST /buildings/{id}/compare`.

**Prompt:**
> Crie a comparação entre duas capturas concluídas do mesmo prédio: baixar as duas nuvens de pontos (pointcloud_key), alinhar com Open3D (ICP), calcular a distância entre elas e gerar ChangeReport (building_id, capture_a, capture_b, stats JSON, heatmap_key) com as regiões de maior variação. Preferência: CloudCompare CLI com plugin M3C2 rodando headless em imagem Docker própria (Ubuntu + pacote cloudcompare) chamada pela task; se a instalação headless travar o progresso, implemente v1 com distância ponto-a-ponto do Open3D e registre o débito neste ROADMAP para trocar por M3C2 depois.

**Aceite:** duas capturas do mesmo prédio produzem relatório com as diferenças destacadas.

---

### Etapa 8 — RAG de orçamento — *Sessão 9 do guia*

**Objetivo:** o LLM sugere orçamento **fundamentado nas obras já executadas**, nunca de cabeça.
**Toca em:** `infra/docker-compose.yml` (+serviço `qdrant`), novo `app/rag/`, modelo `Project` (histórico de obras), endpoint `POST /captures/{id}/budget-draft`.

**Prompt:**
> Adicione o serviço qdrant ao compose; crie o modelo Project para obras executadas (descrição, quantitativos, custos finais, prazo real) com endpoint de cadastro; indexe cada Project no Qdrant usando embeddings (sentence-transformers multilíngue, ex. paraphrase-multilingual-MiniLM); crie POST /captures/{id}/budget-draft que busca os k projetos mais similares ao quantitativo atual e chama o LLM (chave/modelo via config) com esse contexto para gerar memorial descritivo + estimativa, retornando também QUAIS projetos embasaram a resposta. Sem histórico indexado, o endpoint responde 409 explicando que precisa de obras cadastradas — nunca inventa preço.

**Aceite:** resposta cita os projetos-fonte; sem histórico, recusa com mensagem clara.

---

### Etapa 9 — Dashboard web + relatórios — *Sessão 10 do guia*

**Objetivo:** um lugar só para ver modelo 3D, medidas, quantitativos e patologias — e exportar PDF.
**Toca em:** `frontend/` (novo, React + Vite), endpoint de URL pré-assinada (`GET /captures/{id}/assets/{kind}/url`), task de PDF (`WeasyPrint`).

**Prompt:**
> Crie o dashboard web em frontend/ (React + Vite): login, lista de prédios/capturas com status, página da captura com viewer 3D (three.js OBJLoader carregando a malha via URL pré-assinada do MinIO — crie o endpoint GET /captures/{id}/assets/mesh/url no backend), medidas, quantitativos, patologias e botão "Gerar relatório" que dispara task Celery gerando PDF (WeasyPrint) com medidas + fotos + patologias, salvo em buildings/{id}/reports/ e baixável.

**Aceite:** do login ao PDF em um fluxo só, sem tocar na API na mão.

---

### Etapa 10 — Inteligência comercial + IFC + API pública — *Sessões 11-12 do guia*

**Objetivo:** fechar a plataforma: precificação com base no realizado, exportação BIM e integração externa.
**Toca em:** `app/rag/` (extensão), novo `workers/ifc_export.py` (+`ifcopenshell`), API keys + webhooks.

**Prompt:**
> Três entregas: 1) estenda o RAG para sugerir margem/risco/prazo comparando previsto × realizado dos Projects; 2) task "ifc.export" com ifcopenshell gerando um .ifc básico do prédio (geometria da malha + propriedades: áreas, altura, quantitativos) salvo em buildings/{id}/exports/; 3) autenticação por API key para integrações externas e webhook configurável disparado em capture.completed com o payload da medição. Documente os três no README.

**Aceite:** .ifc abre em visualizador BIM; webhook chega num endpoint de teste.

---

## 8. Rotina de cada sessão no Claude Code

1. Abrir o repositório e anexar `ROADMAP.md` + `docs/roadmap.md`.
2. Colar o prompt da etapa da vez (um por sessão — não misturar etapas).
3. Ao final: revisar o diff, conferir o checklist da seção 5 do `docs/fable5-guia-execucao.md` (dependência vs. código copiado; testes escritos e rodados; números validados contra referência real nas etapas que tocam precisão).
4. Atualizar a tabela de status (seção 2) e commitar tudo junto.
5. Etapas que tocam precisão (**0, 4, 6, 7**): não marcar ✅ sem comparação com medição/observação real de campo.
