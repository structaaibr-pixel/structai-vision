# Relatórios de calibração

Cada execução de `scripts/calibrate.py` grava aqui um JSON com: dataset/fonte,
qualidade do ODM, imagens usadas/descartadas, medidas da malha, resíduos de GCP
(RMS 3D), comparação com referência manual (quando houver `--truth`) e o
veredito APROVADO/REPROVADO.

**Commite estes arquivos**: eles são o histórico de acurácia do sistema —
a série que comprova a margem de erro real e cumpre o Gate de medição
(ROADMAP.md, seção 6; metodologia em `docs/calibracao.md`).
