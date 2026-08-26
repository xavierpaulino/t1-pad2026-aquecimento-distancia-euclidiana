# T1: Aquecimento - Distância Quadrática entre Vetores

Este repositório contém a implementação e a infraestrutura experimental utilizadas
para avaliar o desempenho do cálculo da distância quadrática entre um vetor de
referência e um conjunto de vetores com diferentes tamanhos.

Para um vetor de referência `q` e um conjunto de vetores `x_i`, é calculada:

D(q, x_i) = Σ_j (q_j - x_ij)²

para cada vetor do conjunto.

A implementação separa a alocação de memória e a inicialização
dos dados da região cronometrada. Somente o cálculo das distâncias e o
armazenamento dos resultados fazem parte da aferição de tempo.

## 1. Requisitos

Os experimentos foram desenvolvidos para um sistema Linux x86-64.

São necessários:

- GCC com suporte a C++20;
- GNU Make;
- Python 3;
- `taskset`;
- pacotes Python:
  - NumPy;
  - pandas;
  - Matplotlib.

Ferramentas opcionais para análise complementar:

- `perf`;
- `lscpu`.

## 2. Clonar o repositório

Clone o repositório e acesse seu diretório:

    git clone <URL-DO-REPOSITORIO>
    cd vector-distance

Substitua `<URL-DO-REPOSITORIO>` pelo endereço deste repositório no GitHub.

## 3. Criar o ambiente Conda

Recomenda-se utilizar um ambiente Conda separado para as dependências Python:

    conda create -n t0_vector_distance python=3.12 numpy pandas matplotlib -c conda-forge
    conda activate t0_vector_distance

O benchmark C++ deve ser compilado com o GCC do sistema, e não com um compilador
C++ fornecido pelo ambiente Conda.

Defina explicitamente:

    export CXX=/usr/bin/g++

Confirme o compilador que será utilizado:

    $CXX --version

Essa separação permite utilizar o Conda para a infraestrutura de análise em
Python, mantendo o benchmark C++ associado ao toolchain nativo da máquina.

## 4. Limpar e compilar o projeto

Remova artefatos de compilações anteriores:

    make clean

Compile a versão otimizada do benchmark:

    make release

As opções de compilação utilizadas no experimento estão definidas no
`Makefile`. A versão otimizada utiliza, entre outras opções:

    -O3
    -march=native

A opção `-march=native` faz com que o código seja otimizado para a arquitetura
da máquina na qual a compilação é realizada. Por esse motivo, o processador e
as opções de compilação devem ser registrados juntamente com os resultados.

## 5. Verificar a corretude da implementação

Antes de realizar qualquer aferição de desempenho, execute o teste interno:

    make test

Uma execução bem-sucedida deve apresentar:

    SELF_TEST_OK

A campanha experimental não deve ser executada caso esse teste falhe.

## 6. Gerar o relatório de vetorização

Para obter evidências das otimizações e da vetorização realizadas pelo
compilador, execute:

    make vectorization

O relatório produzido é armazenado em:

    build/vectorization.txt

Esse arquivo permite verificar quais trechos foram ou não vetorizados pelo
compilador. A ocorrência de vetorização não deve ser inferida apenas a partir
dos tempos observados.

## 7. Calibrar o experimento

Antes da campanha experimental oficial, execute:

    python scripts/calibrate_n.py

A calibração determina um valor adequado e constante de `N` para a máquina
utilizada, considerando principalmente a memória necessária para executar a
maior configuração do experimento.

A calibração também:

- identifica os CPUs lógicos permitidos ao processo;
- considera a topologia dos cores físicos;
- seleciona deterministicamente um CPU lógico;
- evita o CPU 0 quando existe outro core físico disponível;
- registra o CPU selecionado;
- caracteriza o mecanismo de temporização;
- mede a menor configuração, correspondente a `T = 32`;
- compara o custo do temporizador com o tempo do kernel;
- registra as evidências utilizadas na decisão.

Uma calibração aceita deve apresentar:

    Calibration accepted

A calibração produz os arquivos:

    config/experiment.conf
    config/calibration.json

Esses arquivos devem ser preservados, pois documentam a configuração utilizada
na campanha experimental.

### Configuração obtida na máquina do experimento de referência

Na máquina utilizada para gerar os resultados disponibilizados neste
repositório, a calibração selecionou:

    N = 16384
    CPU = 2

Esses valores são específicos da máquina experimental e não devem ser
considerados automaticamente adequados para outra plataforma.

Na calibração de referência, a maior alocação principal, correspondente a
`T = 4096`, foi estimada em aproximadamente:

    512,2 MiB

Para `T = 32`, foi obtido um tempo mediano de aproximadamente:

    0,530868 ms

O custo mediano de leituras consecutivas do temporizador foi:

    32 ns

correspondendo a aproximadamente:

    0,006028%

do tempo mediano da menor configuração.

## 8. Inspecionar a configuração calibrada

Antes de iniciar a campanha experimental, verifique a configuração:

    cat config/experiment.conf

A política de seleção do CPU também pode ser inspecionada com:

    python scripts/cpu_selection.py --json

Depois da calibração, `N` e o CPU selecionado devem permanecer constantes
durante toda a campanha experimental.

Eles não devem ser alterados posteriormente em função dos resultados obtidos.

## 9. Executar a campanha experimental

Execute:

    ./scripts/run_experiments.sh

A campanha avalia os seguintes tamanhos de vetor:

    T = 32
    T = 64
    T = 128
    T = 256
    T = 512
    T = 1024
    T = 2048
    T = 4096

O valor de `N` permanece constante para todos os tamanhos de vetor.

### Região cronometrada

Não fazem parte da região cronometrada:

- alocação de memória;
- inicialização dos vetores;
- geração dos valores;
- leitura de arquivos;
- escrita de arquivos;
- apresentação dos resultados.

A região aferida corresponde exclusivamente ao cálculo das distâncias dos
`N` vetores em relação ao vetor de referência e ao armazenamento dos
resultados calculados.

### Repetições

Cada tamanho `T` é aferido repetidamente para permitir a caracterização da
variabilidade experimental.

As execuções de aquecimento (`warm-up`) são realizadas antes das observações
consideradas na análise e não fazem parte dos tempos reportados.

A campanha utiliza uma ordem intercalada dos tamanhos de vetor para reduzir a
associação sistemática entre um determinado valor de `T` e o momento temporal
da campanha.

## 10. Analisar os resultados

Após o término da campanha experimental, execute:

    python scripts/analyze_results.py

Esse script calcula os índices de desempenho e as estatísticas derivadas das
aferições brutas.

Em seguida, gere os gráficos:

    python scripts/plot_results.py

## 11. Arquivos de resultados

Entre os arquivos produzidos pela campanha e pela análise estão:

    data/raw_measurements.csv
    data/measurements_with_metrics.csv
    data/summary.csv

### `raw_measurements.csv`

Contém as observações individuais de tempo obtidas durante a campanha.

Esse arquivo representa os dados experimentais brutos e deve ser preservado
sem alterações.

### `measurements_with_metrics.csv`

Contém as aferições juntamente com os índices de desempenho derivados.

### `summary.csv`

Contém as estatísticas utilizadas para sintetizar e comparar os resultados
dos diferentes tamanhos de vetor.

Os gráficos gerados permitem analisar, entre outros aspectos:

- tempo de execução;
- variabilidade do tempo de execução;
- vetores processados por segundo;
- elementos processados por segundo;
- crescimento normalizado do tempo;
- tempo por elemento processado.

## 12. Índices de desempenho

Considerando:

- `N`: número de vetores;
- `T`: número de elementos de cada vetor;
- `t`: tempo de execução em segundos;

a taxa de processamento de vetores é calculada por:

    Pv = N / t

em vetores por segundo.

A taxa de processamento de elementos é:

    Pe = (N * T) / t

em elementos por segundo.

Também é utilizado o custo temporal por elemento:

    ns_por_elemento = (t * 10^9) / (N * T)

expresso em nanossegundos por elemento.

Esse último índice auxilia na análise do custo computacional por unidade de
trabalho à medida que `T` aumenta.

## 13. Sequência completa para reprodução

Após clonar o repositório, uma execução completa pode ser realizada com:

    conda activate t0_vector_distance

    export CXX=/usr/bin/g++

    make clean
    make release
    make test
    make vectorization

    python scripts/calibrate_n.py

    cat config/experiment.conf

    ./scripts/run_experiments.sh

    python scripts/analyze_results.py
    python scripts/plot_results.py

Recomenda-se executar a campanha em uma máquina sem outras cargas
computacionalmente intensivas concorrentes.

## 14. Reprodutibilidade

Para permitir a reprodução e auditoria do experimento, devem ser preservadas
informações sobre:

- processador utilizado;
- topologia da CPU;
- sistema operacional;
- compilador e sua versão;
- opções de compilação;
- versão do Python;
- ambiente Conda;
- CPU lógico selecionado;
- valor calibrado de `N`;
- valores de `T`;
- seed utilizada na geração dos dados;
- mecanismo de temporização;
- caracterização do custo do temporizador;
- dados brutos das aferições;
- estatísticas derivadas;
- informações de vetorização produzidas pelo compilador.

## 15. Reprodução em outra máquina e auditoria dos resultados

Existem dois procedimentos distintos.

### Reproduzir a metodologia em outra máquina

Ao executar o benchmark em outra máquina, deve-se realizar novamente:

    python scripts/calibrate_n.py

Isso permite selecionar `N` e CPU de acordo com as características da nova
plataforma.

Não se deve assumir que:

    N = 16384
    CPU = 2

sejam apropriados para outra máquina.

### Auditar os resultados deste repositório

Para verificar os resultados reportados neste trabalho, devem ser utilizados
os arquivos originais preservados no repositório, incluindo:

    config/experiment.conf
    config/calibration.json
    data/raw_measurements.csv
    data/measurements_with_metrics.csv
    data/summary.csv
    build/vectorization.txt

Dessa forma, as estatísticas e figuras apresentadas podem ser rastreadas até
as observações experimentais originais.

## 16. Observações metodológicas importantes

O valor de `N` é determinado antes da campanha experimental e permanece
constante para todos os valores de `T`.

A afinidade de CPU também é determinada antes da campanha e permanece
inalterada durante o experimento.

A seleção do CPU utiliza a topologia do processador e não realiza testes em
vários CPUs para escolher posteriormente aquele que apresenta o menor tempo.

Os dados utilizados nos cálculos são gerados e inicializados antes da região
cronometrada.

As execuções de aquecimento não são incluídas nas aferições reportadas.

As observações brutas são preservadas.

Valores discrepantes não são automaticamente removidos apenas por diferirem
das demais observações. A variabilidade observada faz parte da análise
experimental.

As decisões fundamentais do protocolo experimental são estabelecidas antes
da análise dos resultados e não são posteriormente modificadas com o objetivo
de produzir uma tendência de desempenho específica.
