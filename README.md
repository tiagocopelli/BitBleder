# 🕹️ BitBlender - EmbarcaHack

BitBlender é um projeto de interface interativa que conecta um joystick da placa BitDogLab para controlar a Viewport do Blender em tempo real via UDP, com suporte adicional a comandos por voz através do Google Cloud Speech-to-Text.
Ideal para artistas 3D, educadores ou desenvolvedores que desejam explorar novas formas de interagir com o Blender, o BitBlender oferece modos de navegação personalizados e feedback visual em tempo real.


## 🔧 Funcionalidades

- 🎮 Controle de navegação no Blender com joystick analógico (modo orbital e modo livre)
- 🌐 Comunicação via UDP entre BitDogLab e o Blender
- 🧠 Comandos de voz ativados por botão físico com reconhecimento de fala via Google Cloud
- 🛑 Zona morta (deadzone) para evitar movimentações acidentais do joystick

## ⚙️ Hardware Utilizado

- BitDogLab
- Módulo Joystick Analógico (Eixos X/Y + Botão)
- Conexão Wi-Fi
- Botões físicos extras (para alternar modos e ativar voz)

## 💻 Software Utilizado

- [Blender](https://www.blender.org/) com Addon personalizado
- Google Cloud Speech-to-Text API (reconhecimento de voz)
- Protocolo UDP para comunicação de rede

### 2. Blender Addon

- Copie a pasta `bitblender-addon/` para sua pasta de addons
- No Blender vai na aba Scripting 
- Open, encontre o código BitBlender.py e abra ele.
- De um play no código. 
- Configure o IP/porta local para escutar os pacotes UDP enviados pela BitDogLab
- Tem que instalar as bibliotecas do Google dentro do Blender para funcionar


### 3. Google Cloud Speech-to-Text

- Crie um projeto no [Google Cloud Console](https://console.cloud.google.com/)
- Ative a API de Speech-to-Text
- Baixe a chave JSON e configure no script de reconhecimento de voz
- Use bibliotecas Python como `speech_recognition` e `pyaudio`

## 🎥 Demonstração
![BitBlender Demo](https://raw.githubusercontent.com/tiagocopelli/BitBleder/refs/heads/main/bloggif_682d2ff63791f.gif)

## 🧠 Comandos por Voz (Exemplos)
- `"renderizar"` → inicia renderização
- `"cubo"` → Abre um cubo
- `"modo orbital"` / `"modo livre"` → troca o modo de navegação

## 🙋‍♂️ Autor
Desenvolvido por [Tiago Lauriano Copelli](https://github.com/tiagocopelli)  
Residência Tecnológica em Sistemas Embarcados  

## 📜 Licença
Este projeto está licenciado sob a [MIT License](LICENSE).

## 🤝 Contribuições
Contribuições são bem-vindas! Sinta-se à vontade para abrir issues, enviar pull requests ou sugerir melhorias.
