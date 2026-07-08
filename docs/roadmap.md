# StructAI Vision — Roadmap de Implementação

**Módulo:** medição automática de m² de fachadas prediais via foto, vídeo e drone, para geração de quantitativo de orçamento de reformas.

**Última atualização:** julho de 2026

---

## 1. Diagnóstico

Medir área é um problema de **geometria e fotogrametria**, não de linguagem. Um LLM multimodal (Groq ou qualquer outro) não reconstrói a cena em 3D — ele estima a partir de padrões visuais aprendidos, sem grounding métrico real. É por isso que a precisão atual não é confiável.

A arquitetura correta separa responsabilidades:

```
Captura → Reconstrução 3D → Cálculo de área → IA gera o orçamento
```

O LLM entra só no final, para interpretar números já calculados — nunca para "adivinhar" a medida a partir da imagem crua.

---

## 2. Riscos técnicos críticos (ler antes de qualquer código)

Estes três pontos decidem se o projeto funciona. Nenhum deles se resolve "de graça" só por escolher os repositórios certos.

### 2.1 Fachadas são um caso difícil para fotogrametria clássica (SfM)
Janelas repetidas em grade e paredes lisas/pintadas confundem o *feature matching* — o algoritmo pode confundir uma janela com a vizinha, ou não encontrar pontos de referência suficientes em superfícies uniformes.

**Mitigação:** protocolo de captura rígido (sobreposição de 70–80% entre fotos, ângulos oblíquos além de frontais, boa iluminação) e conferência manual da reconstrução nos primeiros prédios processados.

### 2.2 Escala métrica não vem de graça
Reconstrução a partir de fotos gera um modelo em escala **relativa**, não absoluta. GPS de drone comum (sem RTK) erra de 1 a 3 metros — inútil para medição de precisão.

**Mitigação:** pontos de controle (GCPs) — 4 a 5 pontos de alto contraste, visíveis em pelo menos 3 fotos, com distância real medida em campo (trena ou medidor a laser). Não precisa ser coordenada GPS verdadeira, só precisa ser consistente. O mesmo protocolo serve para captura por drone ou por celular.

### 2.3 Velocidade de processamento não é automática
Reconstrução densa (SfM + MVS) sobre centenas de frames de vídeo é pesada. Sem GPU de servidor dedicada, o processamento pode ficar mais lento que a medição manual — o oposto do objetivo do projeto.

**Mitigação:** dimensionar infraestrutura de GPU desde o início e tratar o processamento como assíncrono (o técnico não espera o resultado na hora, recebe depois).

> **Antes de escrever qualquer código de app**, valide os três pontos acima em 2–3 prédios reais (ver Fase 0).

---

## 3. Tecnologias avaliadas

| Tecnologia | Papel | Observação |
|---|---|---|
| **OpenDroneMap (ODM)** | Motor de reconstrução principal | Embala OpenSfM (matching/pose) + OpenMVS (densificação) internamente. Suporte nativo a GCP. Processa imagem de drone e terrestre. WebODM já inclui ferramenta de medir área/volume/comprimento. |
| **COLMAP** | Alternativa / validação cruzada | Referência da indústria em precisão; útil para checar resultados do ODM em casos difíceis. |
| **OpenSfM** (repo original, Mapillary) | Evitar como dependência direta | Há sinais de manutenção reduzida (um fork recente alega isso, embora o repo oficial ainda tenha commits). Usar via ODM em vez de integrar diretamente. |
| **OpenCV** | Pré-processamento | Correção de distorção de lente, detecção de nitidez, alinhamento de imagens. |
| **YOLO** | Detecção de objetos | Janelas, portas, ar-condicionado, sacadas, marquises, calhas, platibandas. |
| **SAM2** | Segmentação | Separa fachada de céu, vizinhança e objetos. |
| **ABECIS** | Detecção de fissuras pronta (Fase 7) | Software livre feito especificamente para inspeção de fissuras em fachada, testado com drone e celular, já gera relatório quantitativo. Testar antes de treinar modelo próprio do zero. |
| **CloudCompare + M3C2** | Comparação entre inspeções (Fase 8) | Software livre (GPL) para diferença entre duas nuvens de pontos ao longo do tempo. A variante M3C2-PM é indicada para nuvens geradas por fotogrametria. Tem API de linha de comando. |
| **Open3D** | Alinhamento de nuvens de pontos | Biblioteca Python para registro/ICP — alinha duas capturas antes de rodar o M3C2. |
| **Nerfstudio** | Visualização 3D navegável (Fase 10) | Framework open source que unifica treino de NeRF e Gaussian Splatting. |
| **IfcOpenShell** | Integração BIM (Fase 12) | Toolkit open source padrão da indústria para ler/gerar arquivos IFC. |
| **Whisper** | Transcrição de voz em campo (Fase 2) | O técnico narra a inspeção em áudio; transcrição automática alimenta o laudo. |
| **Qdrant / Weaviate / ChromaDB** | Orçamento fundamentado em histórico (Fase 11) | Banco vetorial + RAG sobre obras já executadas, para o LLM sugerir valor/margem com base em dado real, não estimativa solta. |
| **Gaussian Splatting** | Só visualização (fase final) | Erro geométrico médio de ~7–8 cm — bom para "passeio 3D", **não confiável para o quantitativo de orçamento**. |
| **LiDAR do iPhone / RoomPlan** | Não recomendado para este caso | Alcance prático de ~5 m, pensado para cômodos internos — não alcança fachada de prédio alto vista da rua. |

---

## 4. Arquitetura

```
Captura (App)
 ├─ Drone            → geometria geral, prédios altos
 └─ Celular (zoom)   → close-ups, detecção futura de patologias
        │
        ▼
Pré-processamento
 • Extração de frames (vídeo → imagens)
 • Filtro de qualidade (remove borrado/duplicado)
 • Correção de distorção de lente (OpenCV)
        │
        ▼
Calibração de escala
 • Arquivo de GCP (pontos de controle medidos em campo)
        │
        ▼
Reconstrução 3D — OpenDroneMap (ODM)
 • OpenSfM interno  → nuvem de pontos esparsa + pose de câmera
 • OpenMVS interno  → densificação + malha 3D
        │
        ▼
Segmentação (IA)
 • YOLO → janelas, portas, ar-condicionado, sacadas
 • SAM2 → fachada vs. fundo
        │
        ▼
StructAI Measure Engine
 • Área total / área líquida (descontando aberturas)
 • Perímetro, altura, volume
        │
        ▼
IA de orçamento (LLM)
 • Memorial descritivo, quantitativos, estimativa de custo
```

---

## 5. Fases de implementação

### Fase 0 — Prova de conceito (gate obrigatório)
**Não avançar para a Fase 1 sem concluir esta etapa.**
- Selecionar 2–3 prédios reais e variados (baixo/alto, textura simples/complexa)
- Capturar com celular *e* drone em cada um, usando o protocolo de GCP (seção 6)
- Processar no ODM (linha de comando ou WebODM)
- Comparar o m² resultante com medição manual (trena/laser)
- Definir com o time comercial qual erro é aceitável (ex.: ±2–5%) e confirmar que o pipeline atinge essa margem
- **Critério de saída:** precisão validada em campo, não apenas em teoria

### Fase 1 — Arquitetura base
- Backend Python (FastAPI)
- PostgreSQL + PostGIS
- Armazenamento de imagens/vídeos (MinIO ou S3)
- Fila assíncrona (Redis + Celery) — a reconstrução 3D nunca deve ser síncrona
- Autenticação, API REST, logs e monitoramento

### Fase 2 — Captura inteligente (app)
- Fluxo de foto/vídeo pelo celular + importação de imagens de drone
- Orientação em tempo real: distância, sobreposição, iluminação, ângulo
- Fluxo guiado para marcar/fotografar os GCPs em campo
- Gravação de áudio com transcrição automática (**Whisper**) para o técnico narrar observações sem precisar digitar em campo

### Fase 3 — Pipeline de reconstrução
- Integração com ODM (CLI ou NodeODM via API HTTP)
- Pré-processamento: extração de frames, filtro de nitidez, correção de distorção
- Exportação de malha, nuvem de pontos e ortomosaico

### Fase 4 — Segmentação e detecção
- YOLO treinado para elementos de fachada (janelas, portas, ar-condicionado, sacadas, marquises, calhas, pingadeiras, platibandas, letreiros)
- SAM2 para separar fachada do entorno
- Áreas discriminadas por classe

### Fase 5 — Motor de medição (StructAI Measure Engine)
- Área, perímetro, altura, volume e inclinação a partir da malha georreferenciada
- Descontos automáticos de aberturas
- Loop de validação contínua contra medições de campo

### Fase 6 — Quantitativos de orçamento
- Pintura (m² líquido), textura (m²), impermeabilização (m²), pastilhas (m²)
- Rejuntes, juntas de dilatação, rodapés, corrimãos, guarda-corpo (metros lineares)

### Fase 7 — Detecção de patologias
- Fissuras, trincas, infiltração, eflorescência, ferragem exposta, desplacamento, bolhas, descascamento, mofo, umidade
- Cada ocorrência com localização, gravidade e área afetada
- Ponto de partida: **ABECIS** — software livre já pronto para detecção de fissuras em fachada, testado com drone e celular; validar antes de treinar modelo próprio do zero
- Para modelo próprio: dataset **omnicrack30k** e a lista **Awesome-Crack-Detection** reúnem os datasets públicos mais usados da área
- As fotos de celular com zoom importam mais aqui do que as imagens de drone

### Fase 8 — Digital Twin
- Histórico por prédio: inspeções, modelos 3D, fotos, orçamentos, manutenções
- Comparação automática entre inspeções ao longo do tempo (novas fissuras, desgaste, evolução de patologias)
- Ferramenta recomendada: **CloudCompare** com o plugin **M3C2** para calcular a diferença entre duas nuvens de pontos de datas diferentes; **Open3D** para alinhar as nuvens (registro/ICP) antes de comparar

### Fase 9 — Orçamento inteligente (LLM)
- Memorial descritivo, cronograma, lista de materiais, equipe e equipamentos
- Gerado a partir dos quantitativos já calculados — nunca a partir da imagem crua

### Fase 10 — Dashboard e relatórios
- Modelo 3D navegável (aqui, sim, pode entrar Gaussian Splatting — só visualização), treinado/renderizado com **Nerfstudio**
- Medidas, quantitativos, patologias, fotos, custos, evolução da obra
- Exportação de PDF técnico, laudo, ART, checklist, relatório fotográfico

### Fase 11 — Inteligência comercial e aprendizado contínuo
- Sugestão de valor, margem, risco e prazo por orçamento
- Cada obra executada realimenta o sistema (produtividade real, consumo, desperdício, tempo de execução)
- Implementar com RAG: banco vetorial (**Qdrant**, **Weaviate** ou **ChromaDB**) indexando obras já executadas, para o LLM buscar projetos parecidos em vez de estimar preço sem referência

### Fase 12 — Escala (SaaS)
- APIs públicas, SDK, webhooks
- Integração com BIM, CAD, ERPs, CRMs e sistemas de manutenção predial — usar **IfcOpenShell** (toolkit open source padrão da indústria) para ler/gerar arquivos IFC

---

## 6. Protocolo de captura em campo (resumo operacional)

1. **Antes de fotografar:** medir e marcar 4–5 pontos de referência com trena/laser (GCPs)
2. **Drone:** voo com sobreposição acima de 70%, fotos oblíquas *e* frontais
3. **Celular:** caminhar ao longo da fachada, filmar/fotografar com sobreposição alta; incluir close-ups das áreas que serão avaliadas por patologia depois
4. **Registro:** anotar as distâncias reais dos GCPs no arquivo de calibração antes de processar
5. **Vídeo:** filtrar frames borrados/redundantes antes de enviar ao pipeline — vídeo gera muito frame ruim, e isso quebra a reconstrução

---

## 7. MVPs sugeridos

| MVP | Escopo | Depende de |
|---|---|---|
| **MVP 0** | Prova de conceito de precisão (sem app) | Fase 0 |
| **MVP 1** | Medição de fachada + quantitativo básico de pintura | Fases 1–3, parte da 5–6 |
| **MVP 2** | Modelo 3D completo + detecção automática de janelas/sacadas | Fase 4 completa |
| **MVP 3** | Detecção de patologias + laudos básicos | Fase 7, parte da 10 |
| **MVP 4** | Digital Twin + orçamento inteligente completo | Fases 8, 9, 11–12 |

O MVP 0 não é opcional: é o que confirma se o restante do investimento faz sentido.

---

## 8. Critérios de validação

- Definir com quem hoje faz a medição manual qual erro (%) é aceitável
- Testar em prédios de alturas, texturas de fachada e condições de iluminação diferentes
- Só integrar ao app de produção depois que a Fase 0 confirmar a precisão em campo — não em teoria

---

## 9. Referências

**Reconstrução 3D e medição**
- OpenDroneMap — https://github.com/OpenDroneMap/ODM
- COLMAP — https://github.com/colmap/colmap
- OpenMVS — https://github.com/cdcseacave/openMVS
- OpenSfM — https://github.com/mapillary/OpenSfM

**Visão computacional**
- YOLO (Ultralytics) — https://github.com/ultralytics/ultralytics
- SAM2 — https://github.com/facebookresearch/sam2

**Detecção de patologias**
- ABECIS — https://github.com/SMART-NYUAD/ABECIS
- omnicrack30k — https://github.com/ben-z-original/omnicrack30k
- Awesome-Crack-Detection — https://github.com/nantonzhang/Awesome-Crack-Detection

**Digital Twin / comparação temporal**
- CloudCompare — https://www.cloudcompare.org
- Open3D — https://github.com/isl-org/Open3D

**Visualização 3D**
- Nerfstudio — https://github.com/nerfstudio-project/nerfstudio

**BIM**
- IfcOpenShell — https://github.com/IfcOpenShell/IfcOpenShell

**Voz e áudio**
- Whisper — https://github.com/openai/whisper

**Banco vetorial / RAG**
- Qdrant — https://github.com/qdrant/qdrant
- Weaviate — https://github.com/weaviate/weaviate
- ChromaDB — https://github.com/chroma-core/chroma
