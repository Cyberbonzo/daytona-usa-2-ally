# Daytona USA 2 Power Edition para ROG Ally

Versão 0.1.0 do adaptador Linux x86-64 para **Daytona USA 2 Power Edition Recomp by Johann Ruiz**. O código do jogo publicado em WebAssembly é compilado antecipadamente em código de máquina x86-64 pelo Cranelift do Wasmtime. Na inicialização, o host Python carrega o módulo já compilado. SDL2 fornece a janela, o áudio estéreo e o controle. O renderizador usa wgpu-native, Vulkan e os shaders do projeto original.

## Instalação no Bazzite

Use a versão de 64 bits para AMD/Intel do Bazzite com SDL2, o driver Vulkan, Python e pip. Coloque o ZIP completo da sua cópia da edição Power Edition em `roms/dayto2pe.zip`. Execute `bash preparar.sh` na pasta do projeto para compilar. Os binários, dependências de Python, dados do jogo e arquivos auxiliares ficam nessa pasta. Adicione `jogar.sh` como jogo externo na Steam. O atalho inicia o programa Linux diretamente e usa a resolução da tela.

## Controles

| Comando | Controle |
|---|---|
| Direção | Analógico esquerdo |
| Acelerar e confirmar | RT |
| Frear | LT |
| Ficha e início | View e Menu, respectivamente |
| Marchas 1, 2, 3 e 4 | B, A, X e Y |
| Reduzir ou subir marcha | LB ou RB |
| Câmeras | Direcional |
| Pausar e retomar | Clique no analógico direito ou Esc |

O jogo começa em neutro. Na transmissão manual, selecione a primeira marcha com B. A instalação usa a configuração de um gabinete e grava os dados em `state/save/`. O multiplayer por rede do projeto web está fora desta versão.

## Dificuldade

O gabinete oferece Easy, Normal, Hard e Hardest. Para consultar o nível, execute `python3 src/difficulty.py`. Com o jogo fechado, `python3 src/difficulty.py Easy` seleciona Easy e mantém a SRAM de recordes.

## Créditos

Daytona USA 2 Power Edition Recomp by Johann Ruiz. O módulo recompilado, os shaders e a descrição dos pacotes de vídeo vêm do [projeto de Johann Ruiz](https://github.com/johannruiz/daytona-usa-2-web). A implementação Linux da apresentação adapta o seu renderizador Apache-2.0. Consulte LICENSE e NOTICE. A preparação obtém os componentes de terceiros e suas licenças na revisão indicada no script. O jogo e as marcas são da Sega.
