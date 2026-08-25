# Estrutura recomendada do relatório

1. **Introdução e objetivo** — problema, variável independente `T`, `N` mantido constante.
2. **Implementação** — fórmula, tipo `double`, layout contíguo, complexidade O(NT), single-thread e justificativa.
3. **Metodologia experimental** — máquina, software, flags, CPU affinity, geração determinística, calibração de N, warm-up, temporizador e fronteira exata da região aferida.
4. **Métricas e estatística** — tempo, vetores/s, elementos/s, ns/elemento; média, mediana, desvio-padrão, IQR e CV. Explicar qualquer métrica adicional.
5. **Resultados** — tabelas e gráficos, preservando dados brutos no repositório.
6. **Análise** — crescimento do tempo com T; comportamento das taxas; estabilidade/variabilidade; mudanças de regime; comparação entre tempo normalizado e crescimento T/32.
7. **Discussão arquitetural** — somente inferências sustentadas pela CPU/cache reais e, se usados, dados auxiliares de vetorização/perf. Evitar afirmar causalidade por coincidência de tamanhos.
8. **Ameaças à validade** — steady-state/cache quente, DVFS/turbo, atividade do SO, uma única máquina, auto-vectorization dependente do compilador/ISA, escolha de N.
9. **Conclusão** — responder objetivamente o que os experimentos mostraram; não extrapolar além da máquina e configuração testadas.
