# Calibração de medição — metodologia e registro de decisão

**Decisão (julho/2026):** para não travar o desenvolvimento das próximas etapas, o gate de validação da Etapa 0 foi dividido em duas fases. A **Fase A** calibra o pipeline com **datasets públicos confiáveis** que incluem GCPs topográficos medidos em campo por terceiros. A **Fase B** — validação com prédios reais medidos a trena/laser pela nossa equipe — continua **obrigatória antes de usar qualquer número de m² comercialmente**, e vira processo contínuo: cada captura de canteiro com medição manual alimenta o mesmo harness e melhora a confiança do sistema ao longo do tempo.

---

## 1. O que a Fase A (dados públicos) valida — e o que não valida

**Valida:**
- o pipeline completo (imagens + GCP → NodeODM → malha → medidas) funciona de ponta a ponta;
- a **escala métrica** do modelo: os resíduos de GCP (diferença entre a coordenada topográfica medida em campo e a posição reconstruída) ficam dentro do limite — é a métrica padrão de acurácia fotogramétrica;
- as opções de reconstrução escolhidas (qualidade, octree, etc.) produzem resultado consistente.

**NÃO valida:**
- o **nosso protocolo de captura de fachada** (sobreposição, distância, iluminação, GCP com trena em parede) — os datasets públicos são aéreos/nadir, não fachadas;
- números absolutos de área de fachada contra medição manual — isso é a Fase B.

Por isso a regra do ROADMAP permanece: **as etapas de precisão (4, 6, 7) não podem ser marcadas ✅ sem comparação com medição real de campo.**

## 2. Como rodar a Fase A

```bash
# 1. suba o NodeODM
docker run -d -p 3000:3000 opendronemap/nodeodm

# 2. dependências do script (mesmas da Sessão 0)
pip install pyodm opencv-python-headless "numpy<2" trimesh shapely

# 3. rode a calibração (comece pelo menor dataset)
python scripts/calibrate.py --list
python scripts/calibrate.py --dataset copr --fast   # smoke test (~minutos-1h em CPU)
python scripts/calibrate.py --dataset copr          # relatório oficial (qualidade high)
python scripts/calibrate.py --dataset bellus        # confirmação com um segundo dataset
```

**Critério de aprovação padrão:** RMS 3D dos resíduos de GCP ≤ **0,05 m** (ajustável com `--max-rms`). O veredito sai no console e o relatório completo em `docs/calibracao/relatorios/{nome}_{data}.json` — **commite os relatórios**: eles são o histórico de calibração do sistema.

Datasets registrados em `scripts/calibration_datasets.json` (baixados em runtime, nunca commitados — convenção 1 do ROADMAP):

| Dataset | Fotos | Licença | Fonte |
|---|---|---|---|
| `copr` | 41 | CC BY-SA 4.0 | github.com/OpenDroneMap/odm_data_copr |
| `boruszyn` | 46 | CC-BY (OSM-PL) | github.com/merkato/odm_boruszyn_kap |
| `bellus` | 122 | CC0 1.0 | github.com/OpenDroneMap/odm_data_bellus |

## 3. Fase B — dados reais do canteiro (melhoria contínua)

Quando a equipe capturar um prédio real, medir com trena/laser pelo menos **altura** e, se possível, área de uma região conhecida, e rodar **o mesmo harness**:

```bash
python scripts/calibrate.py --name predio_alfa \
    --images ./capturas/predio_alfa/fotos \
    --gcp ./capturas/predio_alfa/gcp_list.txt \
    --truth ./capturas/predio_alfa/truth.json
```

`truth.json` (use as medidas que tiver; `tolerance_pct` conforme combinado com o comercial):

```json
{"height_m": 12.5, "surface_area_m2": 480.0, "tolerance_pct": 5.0}
```

Cada rodada gera relatório em `docs/calibracao/relatorios/` com o erro percentual por medida. Com 2-3 prédios aprovados, a Fase B do gate está cumprida e o histórico segue crescendo a cada obra — é essa série de relatórios que mostra a margem de erro real do sistema e orienta ajustes no protocolo de captura (a causa nº 1 de erro, ver `docs/roadmap.md` seção 2).

## 4. Encaminhamento no ROADMAP

- Fase A libera o desenvolvimento das Etapas 3+ (código pode andar).
- Fase B continua condicionando: uso comercial dos números, e o ✅ das etapas de precisão (4, 6, 7).
- Futuro (pós-Etapa 2): o app de captura pode pedir a medição manual de referência no próprio fluxo de campo, gravando o `truth.json` automaticamente — transformando cada obra em ponto de calibração sem esforço extra.
