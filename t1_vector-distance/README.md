# Trabalho 1 — Distância entre Vetores

Implementação e protocolo experimental para calcular, para `N` vetores de `T` valores reais,

\[
D(q,x_i)=\sum_{j=0}^{T-1}(q_j-x_{ij})^2.
\]

O projeto foi estruturado para que **somente o cálculo e armazenamento das N distâncias** esteja dentro da região cronometrada. Alocação, geração de dados, inicialização, warm-up, checksum, estatística, escrita de CSV e gráficos ficam fora dela.

## Decisões experimentais

- C++20, precisão `double`.
- Implementação principal single-thread.
- `X` armazenado em um único vetor contíguo em row-major (`X[i*T+j]`).
- Dados pseudoaleatórios determinísticos com `std::mt19937_64` e seed registrada.
- Temporização por `clock_gettime(CLOCK_MONOTONIC_RAW)`.
- Processo preso a um único CPU lógico durante calibração e campanha (`taskset`). A seleção automática é topologia-aware: considera apenas CPUs permitidos, escolhe um representante por core físico e evita CPU 0 quando existe alternativa.
- Warm-up separado das medições oficiais.
- Campanha em blocos randomizados deterministicamente para reduzir correlação entre tamanho `T` e deriva temporal/térmica.
- Todas as repetições são preservadas em `data/raw_measurements.csv`; não há remoção silenciosa de outliers.
- `N` é escolhido antes da campanha por uma calibração separada e depois permanece constante para todos os valores de `T`.
- Compilação experimental padrão: `-O3 -march=native`; existe também alvo portátil com `-O3`.
- O relatório de vetorização do compilador pode ser gerado explicitamente; vetorização não é presumida.

## 1. Dependências

- Linux
- GCC ou Clang com C++20
- Python 3
- NumPy, pandas e Matplotlib para análise/gráficos

Instalação das dependências Python, se necessário:

```bash
python3 -m pip install -r requirements.txt
```

## 2. Compilar e validar corretude

Se o projeto estiver sendo executado dentro de um ambiente Anaconda/Conda, prefira explicitamente o compilador C++ do sistema para o benchmark. Isso evita que o executável de desempenho herde requisitos ISA ou bibliotecas do toolchain Conda que não correspondam à CPU física:

```bash
export CXX=/usr/bin/g++
make clean
make release
make test
```

Fora de Conda, ou quando `CXX` já aponta para o compilador nativo desejado:

```bash
make release
make test
```

O teste deve imprimir `SELF_TEST_OK`.

Para gerar também um relatório do auto-vectorizer do GCC:

```bash
make vectorization
```

O relatório fica em `build/vectorization.txt`.

## 3. Calibrar e validar N

A calibração **não faz parte dos dados oficiais**. Ela escolhe o maior `N` potência de dois cuja alocação principal no pior caso (`T=4096`) permaneça dentro de 25% da memória `MemAvailable` observada. Antes das medições, seleciona deterministicamente um CPU permitido usando a topologia: reduz os SMT siblings a um representante por core físico e evita o CPU lógico 0 sempre que outro core físico está disponível. A escolha é congelada e reutilizada sem alteração na campanha oficial. Na CPU escolhida, caracteriza `CLOCK_MONOTONIC_RAW` e mede `T=32`. O `N` só é aceito se o custo mediano de duas leituras consecutivas do relógio representar no máximo 1% da mediana do kernel em `T=32`. Assim, não se impõe uma duração absoluta arbitrária à região medida.

```bash
python3 scripts/calibrate_n.py
```

Ela cria:

- `config/experiment.conf`: configuração congelada da campanha, incluindo o CPU lógico;
- `config/calibration.json`: evidência da escolha de `N`, memória, amostras de `T=32`, resolução do relógio e razão timer/kernel.

Os limites podem ser alterados de forma explícita. Também é possível substituir conscientemente a escolha automática de CPU durante a **calibração**:

```bash
python3 scripts/calibrate_n.py --memory-fraction 0.20 --max-timer-overhead-pct 0.5 --cpu 2
```

A campanha não escolhe outro CPU dinamicamente: usa obrigatoriamente o valor congelado em `config/experiment.conf` e aborta se esse CPU deixar de estar permitido/online. Isso evita que calibração e medições oficiais ocorram em cores diferentes.

Depois de iniciar a campanha oficial, **não recalibre N para valores diferentes de T**.

## 4. Executar a campanha oficial

```bash
./scripts/run_experiments.sh
```

O script:

1. compila/testa o programa se necessário;
2. usa o `N` congelado em `config/experiment.conf`;
3. captura informações da máquina e ferramentas;
4. fixa o processo a um CPU lógico;
5. distribui as repetições em cinco blocos e randomiza deterministicamente a ordem dos oito valores de `T` dentro de cada bloco;
6. executa todos os `T = 32, 64, 128, 256, 512, 1024, 2048, 4096` o mesmo número total de vezes;
7. preserva cada medição, bloco e posição de ordem em `data/raw_measurements.csv`.

O CPU **não deve ser trocado no momento da campanha**. Para usar outro CPU, faça essa decisão na calibração (`--cpu N`) e gere uma nova configuração antes de iniciar uma nova campanha oficial.

## 5. Analisar

```bash
python3 scripts/analyze_results.py
```

São produzidos:

- `data/summary.csv`;
- `data/measurements_with_metrics.csv`.

Para cada observação são calculados:

- tempo;
- vetores/s;
- elementos/s;
- ns/elemento;
- GFLOP/s sob a convenção explícita de 3 FLOPs por elemento;
- throughput lógico do payload de `X` em GB/s (não rotulado como largura de banda DRAM medida).

Para cada `T`, o resumo inclui mediana, média, desvio-padrão, CV, mínimo, Q1, Q3 e máximo.

## 6. Gerar gráficos

```bash
python3 scripts/plot_results.py
```

Os gráficos PDF e PNG são gravados em `results/`:

- tempo de execução;
- vetores/s;
- elementos/s;
- ns/elemento;
- boxplot de variabilidade;
- crescimento normalizado do tempo vs. crescimento da quantidade de trabalho.

## 7. Região efetivamente aferida

No executável, cada observação oficial é delimitada por:

```cpp
const std::uint64_t start = monotonic_raw_ns();
squared_distances(q.data(), x.data(), distances.data(), n, t);
const std::uint64_t end = monotonic_raw_ns();
```

A função `squared_distances` contém exclusivamente os dois laços que calculam e armazenam as `N` distâncias. Nenhuma alocação, inicialização, E/S ou análise estatística ocorre dentro desse intervalo.

## 8. Reprodutibilidade

A campanha registra:

- `system/system_info.txt`: SO, kernel, CPU, caches, memória, compilador, Python e políticas de frequência disponíveis;
- `system/experiment_parameters.txt`: `N`, seed, repetições, warm-up, CPU lógico, valores de `T` e flags de compilação;
- `config/calibration.json`: escolha de `N`, CPU, orçamento de memória e caracterização do temporizador usada para validar a menor configuração;
- dados brutos individuais em CSV.

O relatório final deve usar essas informações, e não valores lembrados ou copiados manualmente.

## 9. Interpretação metodológica

Com `N` constante, a quantidade de elementos processados é `N*T`. A hipótese de primeira ordem é que o tempo cresça aproximadamente com `T`, mas a análise não deve assumir linearidade perfeita. Mudanças em `ns/elemento`, elementos/s ou variabilidade podem indicar mudança de regime; explicações por cache, SIMD ou memória devem ser sustentadas por informações da máquina e, quando necessário, por evidência adicional (por exemplo, relatório de vetorização ou `perf` em uma campanha auxiliar separada).
