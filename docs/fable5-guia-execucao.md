# StructAI Vision — Guia de Execução com Fable 5

Este documento complementa o `roadmap.md` (arquitetura, riscos técnicos e stack). Aqui está **como** conduzir o Fable 5 sessão por sessão para construir o módulo. Anexe sempre o `roadmap.md` como contexto, além da seção específica abaixo.

---

## 1. Estrutura de repositório

```
structai-vision/
├── docs/
│   └── roadmap.md
├── backend/
├── app/
├── infra/
│   └── docker-compose.yml
├── scripts/
└── README.md
```

Um único repositório, um único dono do código: o que é seu. As ferramentas externas nunca entram como pasta copiada.

---

## 2. Regra de ouro (não negociável)

Dependência declarada, nunca código copiado:
- Bibliotecas Python (YOLO, SAM2, Open3D, Whisper, IfcOpenShell) → `requirements.txt`
- Aplicações pesadas (ODM, CloudCompare, Qdrant) → imagem Docker oficial, orquestrada no `docker-compose.yml`
- Seu backend fala com cada ferramenta via CLI, API HTTP ou import de biblioteca — nunca precisa do código-fonte delas no seu repo

Ao pedir algo ao Fable 5, dê a ele o link da documentação de uso de cada ferramenta, não o código-fonte dela. Exceção: se for preciso fazer fork de algo pra customizar internamente (ex.: fine-tune do YOLO), aí sim é um fork isolado daquele repositório específico — assunto separado deste guia.

---

## 3. Por que essa ordem

Sessão 0 vem antes de tudo porque nenhuma linha de app importa se o núcleo de medição não bate no campo. Da Sessão 1 em diante, cada uma depende da anterior estar de pé (infra → captura → reconstrução → IA → medição → o resto). Não pule a ordem mesmo que pareça mais rápido montar a tela bonita primeiro.

---

## 4. Sessões

### Sessão 0 — Harness de validação (antes de qualquer coisa do app)
**Depende de:** nada. **Objetivo:** confirmar que o núcleo de medição funciona, sem investir em app ainda.

> Crie um script Python standalone (sem framework web, sem banco de dados) que: 1) recebe um diretório de imagens de um prédio e um arquivo de GCP no formato aceito pelo OpenDroneMap; 2) roda o ODM via linha de comando (ou chama uma instância local do NodeODM); 3) lê a malha 3D resultante e calcula área de superfície total e perímetro da base; 4) imprime os resultados em formato legível. Sem interface, autenticação ou persistência — só isso.

**Entrega esperada:** script único, testável localmente.
**Ponto de atenção:** rode isso em 2–3 prédios reais e compare com medição manual (trena/laser) antes de ir para a Sessão 1. Se o erro estiver fora do aceitável, o problema está no protocolo de captura ou na calibração de GCP — volte ao `roadmap.md`, seção 2, antes de seguir.

### Sessão 1 — Arquitetura base
**Depende de:** Sessão 0 validada.

> Monte a arquitetura base do backend do StructAI Vision: FastAPI, PostgreSQL com extensão PostGIS, fila assíncrona com Redis + Celery, armazenamento de arquivos em MinIO (compatível com S3), autenticação JWT, e um docker-compose.yml orquestrando todos os serviços. Inclua endpoint de health-check e estrutura de logs. Ainda sem lógica de negócio — só a fundação.

**Entrega esperada:** stack subindo localmente com `docker-compose up`.

### Sessão 2 — Captura inteligente (app)
**Depende de:** Sessão 1.

> Construa o fluxo de captura do app: tela de gravação de foto/vídeo com orientação em tempo real (sobreposição mínima entre frames, ângulo, distância), tela de importação de imagens de drone, fluxo guiado de marcação dos pontos de GCP (o usuário toca em pontos na imagem e digita a distância real medida em campo), e gravação de áudio com transcrição automática via Whisper para observações do técnico. Sem lógica de reconstrução ainda — só captura e envio pro backend.

**Entrega esperada:** app enviando imagens + arquivo de GCP + áudio transcrito pro backend da Sessão 1.

### Sessão 3 — Pipeline de reconstrução
**Depende de:** Sessões 0 (lógica) e 1 (infra).

> Transforme o script da Sessão 0 em uma tarefa assíncrona (Celery) disparada quando uma nova captura chega na fila. Ela deve chamar o ODM via NodeODM API, armazenar malha, nuvem de pontos e ortomosaico no MinIO, e atualizar o status do processamento no banco. Trate falhas de reconstrução (fachada sem textura suficiente, poucas fotos, baixa sobreposição) retornando um erro claro em vez de travar silenciosamente.

**Entrega esperada:** captura da Sessão 2 processada de ponta a ponta, resultado salvo.

### Sessão 4 — Segmentação e detecção
**Depende de:** Sessão 3.

> Adicione um passo de segmentação após a reconstrução: rode YOLO (biblioteca ultralytics) nas imagens originais para detectar janelas, portas, ar-condicionado e sacadas, e SAM2 para segmentar a fachada do fundo. Salve máscaras e bounding boxes associadas às imagens e, quando possível, projete essas detecções na malha 3D.

**Entrega esperada:** aberturas e elementos discriminados por classe, associados ao modelo 3D.

### Sessão 5 — Motor de medição
**Depende de:** Sessão 4.

> Implemente o StructAI Measure Engine: a partir da malha georreferenciada e das detecções da Sessão 4, calcule área total, área líquida (descontando aberturas), perímetro, altura e volume. Exponha via API.

**Entrega esperada:** endpoint retornando as medidas de um prédio processado.

### Sessão 6 — Quantitativos de orçamento
**Depende de:** Sessão 5.

> A partir da área líquida calculada, implemente as regras de conversão em quantitativos: m² de pintura, m² de textura, m² de impermeabilização, metros lineares de rejunte/juntas/rodapés. As regras devem ser configuráveis, não fixas no código — elas variam por tipo de serviço.

**Entrega esperada:** quantitativo completo gerado a partir de uma medição.

### Sessão 7 — Detecção de patologias
**Depende de:** Sessão 4 (imagens já segmentadas ajudam a localizar a patologia na fachada certa).

> Integre o ABECIS (ou uma API própria treinada sobre o dataset omnicrack30k) para detectar fissuras, infiltração e outras patologias nas imagens de close-up. Cada detecção deve ter localização, gravidade estimada e área afetada, associada à posição na malha 3D.

**Entrega esperada:** lista de patologias detectadas e localizadas por prédio.
**Ponto de atenção:** valide a precisão do ABECIS nas suas próprias fotos antes de decidir se vale treinar um modelo customizado (ver `roadmap.md`, Fase 7).

### Sessão 8 — Digital Twin
**Depende de:** Sessão 5 (precisa de pelo menos duas capturas processadas do mesmo prédio).

> Construa a comparação entre inspeções: dado o modelo 3D de duas datas diferentes do mesmo prédio, use Open3D para alinhar as nuvens de pontos (ICP) e o CloudCompare (via linha de comando, plugin M3C2) para calcular a diferença entre elas. Gere um relatório destacando as áreas com maior variação.

**Entrega esperada:** relatório de mudança entre duas inspeções do mesmo prédio.

### Sessão 9 — Orçamento inteligente (RAG)
**Depende de:** Sessão 6.

> Implemente o RAG de orçamento: indexe os orçamentos e obras já executadas em um banco vetorial (Qdrant ou ChromaDB), e crie um endpoint que, dado um novo quantitativo, busca os projetos mais parecidos do histórico e usa isso como contexto para o LLM gerar o memorial descritivo e a estimativa de custo.

**Entrega esperada:** orçamento gerado com base em dado histórico real, não estimativa solta do LLM.

### Sessão 10 — Dashboard e relatórios
**Depende de:** Sessões 5, 6, 7, 9.

> Construa o dashboard: visualização do modelo 3D navegável (Nerfstudio ou viewer compatível), quantitativos, patologias mapeadas, e exportação de PDF técnico/laudo/relatório fotográfico.

**Entrega esperada:** painel único reunindo os resultados de um prédio.

### Sessão 11 — Inteligência comercial
**Depende de:** Sessão 9.

> Estenda o RAG da Sessão 9 para sugerir valor, margem, risco e prazo, com base em produtividade e custo real das obras anteriores indexadas.

**Entrega esperada:** sugestão de precificação fundamentada em histórico.

### Sessão 12 — Escala (SaaS)
**Depende de:** todas as anteriores estáveis.

> Adicione IfcOpenShell para exportação/importação de arquivos IFC, e exponha APIs públicas + webhooks para integração externa (BIM, CAD, ERP, CRM).

**Entrega esperada:** módulo pronto para integrar com sistemas de terceiros.

---

## 5. Checklist de revisão após cada sessão

- O Fable 5 usou a ferramenta como dependência (pip/Docker) ou tentou copiar código-fonte? Corrigir se for o segundo caso.
- Rodou os testes que ele mesmo escreveu? Pedir para escrever se não escreveu.
- Para sessões que tocam precisão (0, 3, 5, 7, 8): os números batem com uma referência real, não só "parece razoável"?

---

## 6. Gestão de custo: quando usar o Fable 5

Fable 5 é o modelo mais caro da Anthropic — reserve para trabalho longo e complexo, onde o "pensar em várias etapas" compensa o custo:

| Usar Fable 5 | Pode usar um modelo mais barato |
|---|---|
| Sessões 0, 3, 4, 8, 9 — orquestração entre múltiplas ferramentas, tratamento de falha, lógica de RAG | Sessão 1 — setup de infra, é bastante padrão |
| Refatorações grandes, migração entre sessões | Sessão 2, 10 — telas de UI |
| Depuração de um pipeline que já está com várias peças integradas | Sessão 6 — regras de conversão, mecânico |
| | Sessão 12 — CRUD de API pública |

---

## 7. Referência

Arquitetura completa, riscos técnicos e stack: ver `docs/roadmap.md`.
