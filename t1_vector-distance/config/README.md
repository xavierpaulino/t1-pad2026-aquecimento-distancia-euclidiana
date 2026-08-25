# Configuração experimental

Não coloque um valor arbitrário de `N` aqui antes da calibração.

Execute:

```bash
python3 scripts/calibrate_n.py
```

O script criará `experiment.conf` e `calibration.json`. Depois disso, esses dois arquivos representam a decisão experimental congelada e devem ser preservados no repositório juntamente com os resultados oficiais.

A calibração também congela o CPU lógico. Por padrão, a seleção é determinística e baseada na topologia: considera apenas CPUs permitidos, escolhe um representante por core físico e evita CPU 0 quando existe alternativa. Não se usa "CPU menos ocupado" por amostragem instantânea, pois essa escolha dependeria de carga transitória e reduziria a reprodutibilidade.
