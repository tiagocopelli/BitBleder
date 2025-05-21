import bpy
import socket
import threading
import speech_recognition as sr
import os
from google.cloud import speech_v1p1beta1 as speech
from google.oauth2 import service_account
from mathutils import Vector, Quaternion
from bpy.props import EnumProperty, PointerProperty, FloatProperty, BoolProperty, StringProperty
from bpy.types import Operator, Panel, Menu
from datetime import datetime, timedelta

bl_info = {
    "description": "Viewport Joystick Navigation with Voice",
    "blender": (4, 0, 0),
    "category": "3D View",
}

# Variáveis globais
joystick_data = {"x": 0.0, "y": 0.0, "button": False, "zoom": False}
stop_threads = False
modal_operator_instance = None
previous_button_state = False
DEADZONE = 0.1
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# Configurações de voz
mic = sr.Microphone()
voice_recognizer = sr.Recognizer()
voice_recognizer.energy_threshold = 300
voice_recognizer.dynamic_energy_threshold = False
voice_recognizer.pause_threshold = 1.0
is_listening = False
stop_voice_thread = False
last_voice_activation = datetime.now() - timedelta(seconds=10)

# Configurações do Google Cloud Speech
#Credentials Ocultada
GOOGLE_CREDENTIALS_PATH = os.path.join(os.path.dirname(__file__), "Sua Credencial Google Aqui")
google_client = None
if os.path.exists(GOOGLE_CREDENTIALS_PATH):
    credentials = service_account.Credentials.from_service_account_file(GOOGLE_CREDENTIALS_PATH)
    google_client = speech.SpeechClient(credentials=credentials)

def rotate_object(obj, axis, angle):
    """Rotaciona objeto no eixo especificado"""
    if axis == 'X':
        obj.rotation_euler.x += angle
    elif axis == 'Y':
        obj.rotation_euler.y += angle
    obj.keyframe_insert(data_path="rotation_euler")

def process_voice_command(command):
    """Executa comandos no Blender com reconhecimento de voz"""
    command = command.lower().strip()
    context = bpy.context
    context.window_manager.last_voice_command = command
    
    command_map = {
        'cube': ['cubo', 'cube', 'cuba', 'cobrir', 'cobe'],
        'sphere': ['sphere', 'create sphere', 'add sphere', 'ball', 'esfera'],
        'front': ['front', 'forward', 'move front', 'ahead', 'frente'],
        'back': ['back', 'backward', 'move back', 'behind', 'trás', 'tras'],
        'left': ['left', 'move left', 'to left', 'esquerda'],
        'right': ['right', 'move right', 'to right', 'direita'],
        'up': ['up', 'move up', 'rise', 'sobe', 'subir'],
        'down': ['down', 'move down', 'lower', 'desce', 'descer'],
        'render': ['render', 'rende', 'renderizar', 'gravar', 'gerar imagem', 'gerar', 'trava', 'travar'],
        'cylinder': ['cylinder', 'cilindro', 'cili', 'cilindru', 'cilin'],
        'texture': ['texture', 'textura', 'smart', 'testura']
    }
    
    try:
        for action, keywords in command_map.items():
            if any(keyword in command for keyword in keywords):
                print(f"Executing command: {action}")
                
                if action == "cube":
                    bpy.ops.mesh.primitive_cube_add()
                elif action == "sphere":
                    bpy.ops.mesh.primitive_uv_sphere_add()
                elif action == "front":
                    bpy.context.space_data.region_3d.view_location.x += 100
                elif action == "back":
                    bpy.context.space_data.region_3d.view_location.x -= 100
                elif action == "left":
                    bpy.context.space_data.region_3d.view_location.y += 100
                elif action == "right":
                    bpy.context.space_data.region_3d.view_location.y -= 100
                elif action == "up":
                    bpy.context.space_data.region_3d.view_location.z += 100
                elif action == "down":
                    bpy.context.space_data.region_3d.view_location.z -= 100
                elif action == "cylinder":
                    bpy.ops.mesh.primitive_cylinder_add(radius=1, depth=2, location=(0, 0, 0))
                elif action == 'render':
                    # Configura o renderizador
                    scene = bpy.context.scene
                    scene.render.image_settings.file_format = 'PNG'
                    scene.render.filepath = "//renders/render_"
    
                    # Executa de forma assíncrona
                    bpy.app.timers.register(
                        lambda: bpy.ops.render.render('INVOKE_DEFAULT', animation=False),
                        first_interval=0.5
                    )
                    print("Comando de renderização recebido - processando...")

                elif action == "texture":
                    obj = bpy.context.active_object
                    if obj and obj.type == 'MESH':
                        bpy.ops.object.mode_set(mode='OBJECT')
                        bpy.ops.object.select_all(action='DESELECT')
                        obj.select_set(True)
                        bpy.context.view_layer.objects.active = obj
                        bpy.ops.object.mode_set(mode='EDIT')
                        bpy.ops.uv.smart_project(angle_limit=66, island_margin=0.03)
                        bpy.ops.object.mode_set(mode='OBJECT')

                return True
                
        print(f"Command not recognized: {command}")
        return False
        
    except Exception as e:
        print(f"Error executing command: {e}")
        return False

def test_microphone():
    """Testa o microfone usando o Google Cloud Speech-to-Text"""
    global google_client
    
    if not google_client:
        return "Google Cloud credentials not found"
    
    r = sr.Recognizer()
    r.energy_threshold = 400
    r.pause_threshold = 0.8
    
    with sr.Microphone() as source:
        try:
            print("Ajustando para ruído ambiente...")
            r.adjust_for_ambient_noise(source, duration=2)
            print("Fale agora (aguardando comando)...")
            
            audio = r.listen(source, timeout=5, phrase_time_limit=3)
            
            # Salva o áudio para debug
            audio_file = os.path.join(bpy.app.tempdir, "teste_microfone.wav")
            with open(audio_file, "wb") as f:
                f.write(audio.get_wav_data())
            
            # Configuração do reconhecimento
            config = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
                sample_rate_hertz=44100,
                language_code='pt-BR',
                enable_automatic_punctuation=False,
                model='command_and_search',
                speech_contexts=[{
                    "phrases": ["teste", "cubo", "esfera", "frente", "trás", "render", "renderizar", "cuba", "cilindro", 'textura', 'texture'],
                    "boost": 15.0
                }]
            )
            
            # Envia para o Google Cloud
            audio_content = audio.get_wav_data()
            response = google_client.recognize(
                config=config,
                audio={"content": audio_content}
            )
            
            # Processa os resultados
            if response.results:
                result = response.results[0].alternatives[0]
                process_voice_command(result.transcript)
                return f"Comando: {result.transcript} (Confiança: {result.confidence:.0%})"
            else:
                return "Nenhum comando reconhecido"
                
        except sr.WaitTimeoutError:
            return "Tempo esgotado - nenhum áudio detectado"
        except Exception as e:
            return f"Erro: {str(e)}"

def voice_capture_thread():
    global is_listening, last_voice_activation, google_client
    
    while not stop_threads:
        try:
            if not sr.Microphone.list_microphone_names():
                print("Nenhum microfone detectado!")
                threading.Event().wait(2.0)
                continue
                
            if datetime.now() - last_voice_activation < timedelta(seconds=3):
                if not is_listening:
                    print("Ativando microfone...")
                    is_listening = True
                    
                    with sr.Microphone() as source:
                        try:
                            voice_recognizer.adjust_for_ambient_noise(source, duration=1)
                            print("Pronto para receber comandos...")
                            
                            audio = voice_recognizer.listen(source, timeout=5, phrase_time_limit=7)
                            
                            # Tenta primeiro com o Google Cloud se disponível
                            if google_client:
                                try:
                                    config = speech.RecognitionConfig(
                                        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
                                        sample_rate_hertz=44100,
                                        language_code='pt-BR',
                                        model='command_and_search'
                                    )
                                    audio_content = audio.get_wav_data()
                                    response = google_client.recognize(
                                        config=config,
                                        audio={"content": audio_content}
                                    )
                                    
                                    if response.results:
                                        command = response.results[0].alternatives[0].transcript
                                        print(f"Google Cloud: {command}")
                                        process_voice_command(command)
                                        continue
                                except Exception as e:
                                    print(f"Erro Google Cloud: {e}")
                            
                            # Fallback para reconhecimento local
                            command = voice_recognizer.recognize_google(audio, language='pt-BR')
                            print(f"Reconhecimento local: {command}")
                            process_voice_command(command)
                            
                        except sr.WaitTimeoutError:
                            print("Tempo limite de escuta atingido")
                        except sr.UnknownValueError:
                            print("Não foi possível entender o áudio")
                        except Exception as e:
                            print(f"Erro na captura de voz: {str(e)}")
                    
                    is_listening = False
            else:
                if is_listening:
                    is_listening = False
            
            threading.Event().wait(0.1)
        except Exception as e:
            print(f"Erro crítico na thread de voz: {str(e)}")
            break

def udp_server_thread(port=8080):
    global joystick_data, stop_threads, last_voice_activation
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("", port))
    sock.settimeout(1.0)
    
    print(f"Servidor UDP iniciado na porta {port}")
    
    while not stop_threads:
        try:
            data, _ = sock.recvfrom(1024)
            msg = data.decode().strip()
            
            if "comandoVoz=Ativo" in msg:
                last_voice_activation = datetime.now()
            
            parts = msg.split()
            joystick_data.update({"x": 0.0, "y": 0.0, "button": False, "zoom": False})
            
            for part in parts:
                if '=' in part:
                    key, value = part.split('=', 1)
                    if key == 'VRX':
                        x = int(value)
                        joystick_data["x"] = (x - 2048) / 2048
                    elif key == 'VRY':
                        y = int(value)
                        joystick_data["y"] = (y - 2048) / 2048
                    elif key == 'BTN':
                        joystick_data["button"] = value.lower() == 'pressionado'
                    elif key == 'ZOOM':
                        joystick_data["zoom"] = value.lower() == 'ativo'
                    #elif key == 'Microfone':
                        #joystick_data['Microfone'] = value.lower() == 'ativo'
                    elif key == 'comandoVoz':
                        joystick_data["comandoVoz"] = value.lower() == 'ativo'
            
        except socket.timeout:
            continue
        except Exception as e:
            print(f"Erro UDP: {e}")
    
    sock.close()

class VIEW3D_MT_JoystickPieMenu(Menu):
    bl_label = "Menu do Joystick"
    bl_idname = "VIEW3D_MT_joystick_pie_menu"

    def draw(self, context):
        layout = self.layout
        pie = layout.menu_pie()

        mode = context.mode

        if mode == 'EDIT_MESH':
            pie.operator("mesh.extrude_region_move", text="Extrudar (E)")
            pie.operator("mesh.edge_face_add", text="Criar Face (F)")
            pie.operator("mesh.delete", text="Excluir (X)")
            pie.operator("transform.translate", text="Mover (G)")
            pie.operator("wm.call_menu", text="Adicionar (Shift+A)").name = "VIEW3D_MT_add"
            pie.operator("transform.resize", text="Escalar (S)")
            pie.operator("mesh.select_all", text="Selecionar Tudo (A)").action = 'SELECT'
            pie.operator("mesh.loopcut_slide", text="Corte em Loop (Ctrl+R)")

        elif mode == 'OBJECT':
            pie.operator("transform.translate", text="Mover (G)")
            pie.operator("object.duplicate_move", text="Duplicar (Shift+D)")
            pie.operator("object.delete", text="Excluir (X)")
            pie.operator("wm.call_menu", text="Adicionar (Shift+A)").name = "VIEW3D_MT_add"
            pie.operator("transform.resize", text="Escalar (S)")
            pie.operator("object.origin_set", text="Definir Origem").type = 'ORIGIN_CENTER_OF_MASS'
            pie.operator("object.shade_smooth", text="Sombrear Suave")
            pie.operator("ed.undo", text="Desfazer (Ctrl+Z)")

        elif mode == 'SCULPT':
            pie.operator("sculpt.brush_set", text="Esculpir (Draw)").brush = "DRAW"
            pie.operator("sculpt.brush_set", text="Suavizar (Smooth)").brush = "SMOOTH"
            pie.operator("sculpt.brush_set", text="Inflar (Inflate)").brush = "INFLATE"
            pie.operator("sculpt.brush_set", text="Esmagar (Flatten)").brush = "FLATTEN"
            pie.operator("sculpt.brush_set", text="Garrar (Grab)").brush = "GRAB"
            pie.operator("sculpt.brush_set", text="Camadas (Layer)").brush = "LAYER"
            pie.operator("sculpt.brush_set", text="Preencher (Fill)").brush = "FILL"
            pie.operator("ed.undo", text="Desfazer (Ctrl+Z)")


class VIEW3D_OT_JoystickNavigation(Operator):
    bl_idname = "view3d.joystick_navigation"
    bl_label = "Joystick View Navigation"
    _timer = None
    initial_distance = None

    def execute(self, context):
        global modal_operator_instance
        wm = context.window_manager
        window = context.window

        self.initial_distance = None
        self._timer = None

        if not window:
            for win in wm.windows:
                for area in win.screen.areas:
                    if area.type == 'VIEW_3D':
                        window = win
                        break
                if window:
                    break

        if not window:
            self.report({'ERROR'}, "Não foi possível encontrar uma janela com área 3D.")
            return {'CANCELLED'}

        self._timer = wm.event_timer_add(0.02, window=window)
        wm.modal_handler_add(self)
        modal_operator_instance = self
        self.report({'INFO'}, "Joystick View Navigation iniciado.")
        return {'RUNNING_MODAL'}
    
    def modal(self, context, event):
        global joystick_data, previous_button_state
        wm = context.window_manager

        if event.type in {'MOUSEMOVE', 'LEFTMOUSE', 'MIDDLEMOUSE', 'RIGHTMOUSE'}:
            return {'PASS_THROUGH'}
        
        if event.type == 'TIMER':
            area = next((a for a in context.screen.areas if a.type == 'VIEW_3D'), None)
            if area:
                space = area.spaces.active
                region = getattr(space, "region_3d", None)
                if region:
                    move_speed = wm.joystick_sensitivity * 0.1
                    mode = wm.joystick_mode
                    target_obj = wm.joystick_target
                    dx = joystick_data["x"]
                    dy = -joystick_data["y"]
                    zoom_active = joystick_data.get("zoom", False)
                    deadzone_threshold = 0.1  # valor típico da zona morta

                    if mode == 'ROTATE_X' and target_obj:
                        if abs(dy) > deadzone_threshold:
                            rotate_object(target_obj, 'X', dy * move_speed * 0.5)

                    elif mode == 'ROTATE_Y' and target_obj:
                        if abs(dx) > deadzone_threshold:
                            rotate_object(target_obj, 'Y', dx * move_speed * 0.5)

                    elif mode == 'ORBIT' and target_obj:
                        rot_speed = wm.joystick_orbit_speed * 0.1
                        #deadzone_threshold = 0.05  # valor típico para zona morta

                        if self.initial_distance is None:
                            self.initial_distance = (region.view_location - target_obj.location).length
                            if self.initial_distance < 0.1:
                                self.initial_distance = 3.0

                        # Aplica zona morta
                        if abs(dx) > deadzone_threshold:
                            # Rotação horizontal ao redor do eixo Z global
                            quat_z = Quaternion((0.0, 0.0, 1.0), -dx * rot_speed * 0.05)

                            # Atualiza a rotação da câmera
                            region.view_rotation = quat_z @ region.view_rotation

                            # Mantém a distância do objeto após a rotação
                            region.view_location = target_obj.location + region.view_rotation @ Vector((0.0, 0.0, self.initial_distance))


                    elif mode == 'FREE':
                        # Leitura do joystick
                        dx = joystick_data.get("x", 0.0)
                        dy = joystick_data.get("y", 0.0)
                        zoom_active = joystick_data.get("zoom", False)

                        # Configuração de velocidade e zona morta
                        move_speed = wm.joystick_orbit_speed * 0.1
                        deadzone_threshold = 0.05

                        # Vetores de movimentação baseados na orientação da câmera
                        right = region.view_rotation @ Vector((1.0, 0.0, 0.0))    # mover lateralmente
                        up = region.view_rotation @ Vector((0.0, 1.0, 0.0))       # subir/descer
                        forward = region.view_rotation @ Vector((0.0, 0.0, -1.0)) # avançar/recuar

                        if zoom_active:
                            if abs(dy) > deadzone_threshold:
                                region.view_location += forward * dy * move_speed * 3.0  # mover para frente/trás
                        else:
                            if abs(dx) > deadzone_threshold:
                                region.view_location += right * dx * move_speed          # mover lateralmente
                            if abs(dy) > deadzone_threshold:
                                region.view_location += up * dy * move_speed             # mover verticalmente

                    if joystick_data["button"] and not previous_button_state:
                        bpy.ops.wm.call_menu_pie(name="VIEW3D_MT_joystick_pie_menu")

                    previous_button_state = joystick_data["button"]
                    area.tag_redraw()

        return {'PASS_THROUGH'}

    def cancel(self, context):
        wm = context.window_manager
        if self._timer:
            wm.event_timer_remove(self._timer)
        self.report({'INFO'}, "Joystick View Navigation cancelado.")

class VIEW3D_OT_StartJoystickNavigation(Operator):
    bl_idname = "view3d.start_joystick_server"
    bl_label = "Iniciar Navegação"

    def execute(self, context):
        global stop_threads
        stop_threads = False
        t = threading.Thread(target=udp_server_thread, daemon=True)
        t.start()
        print("Servidor UDP iniciado e aguardando dados do joystick...")
        return bpy.ops.view3d.joystick_navigation()

class VIEW3D_OT_StopJoystickNavigation(Operator):
    bl_idname = "view3d.stop_joystick_server"
    bl_label = "Parar Navegação"

    def execute(self, context):
        global stop_threads, modal_operator_instance
        stop_threads = True
        if modal_operator_instance:
            modal_operator_instance.cancel(context)
            modal_operator_instance = None
        self.report({'INFO'}, "Navegação com joystick parada.")
        return {'FINISHED'}

class VIEW3D_OT_SetMode(Operator):
    bl_idname = "view3d.set_mode"
    bl_label = "Trocar Modo"
    
    mode: EnumProperty(
        name="Modo",
        items=[
            ('OBJECT', "Objeto", ""),
            ('EDIT', "Editar", ""),
            ('SCULPT', "Esculpir", ""),
        ]
    )

    def execute(self, context):
        obj = context.active_object
        if obj:
            try:
                bpy.ops.object.mode_set(mode=self.mode)
                self.report({'INFO'}, f"Modo alterado para: {self.mode}")
            except RuntimeError as e:
                self.report({'ERROR'}, f"Erro ao trocar modo: {e}")
        else:
            self.report({'WARNING'}, "Nenhum objeto ativo para trocar o modo.")
        return {'FINISHED'}

class VIEW3D_OT_ResetViewport(Operator):
    bl_idname = "view3d.reset_viewport"
    bl_label = "Zerar Viewport"
    bl_description = "Reseta a posição da câmera da viewport para a origem"

    def execute(self, context):
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                space = area.spaces.active
                region = getattr(space, "region_3d", None)
                if region:
                    region.view_location = (0.0, 0.0, 0.0)
                    self.report({'INFO'}, "Viewport resetada para (0, 0, 0)")
                    break
        return {'FINISHED'}

class VIEW3D_OT_TestMicrophone(Operator):
    bl_idname = "view3d.test_microphone"
    bl_label = "Testar Microfone"
    bl_description = "Testa o microfone com reconhecimento de voz do Google Cloud"
    
    def execute(self, context):
        result = test_microphone()
        self.report({'INFO'}, result)
        return {'FINISHED'}

class VIEW3D_PT_JoystickPanel(Panel):
    bl_label = "BitBlender Menu"
    bl_idname = "VIEW3D_PT_joystick_view"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'BitBlender'

    def draw(self, context):
        layout = self.layout
        wm = context.window_manager
        obj = context.active_object

        layout.separator()
        # Botão "Iniciar"
        row = layout.row()
        row.operator("view3d.start_joystick_server", icon='PLAY')

        layout.separator()

        # Botão "Parar"
        row = layout.row()
        row.operator("view3d.stop_joystick_server", icon='PAUSE')
        layout.separator()

        row = layout.row()
        row.prop(wm, "joystick_mode", expand=True)
        
        layout.prop(wm, "joystick_sensitivity", slider=True)
        
        if wm.joystick_mode in {'ORBIT', 'ROTATE_X', 'ROTATE_Y'}:
            layout.prop_search(wm, "joystick_target", context.scene, "objects", text="Objeto Alvo")
            
            if wm.joystick_mode == 'ORBIT':
                layout.prop(wm, "joystick_orbit_speed", slider=True, text="Velocidade Orbital")
            else:
                layout.label(text=f"Rotacionando no eixo {'X' if wm.joystick_mode == 'ROTATE_X' else 'Y'}")
        
        
        #layout.separator()
        #layout.label(text="Trocar Modo:")
        #layout.prop(wm, "joystick_shift", toggle=True)

        if obj:
            row = layout.row(align=True)
            row.operator("view3d.set_mode", text="Objeto").mode = 'OBJECT'
            if obj.type == 'MESH':
                row.operator("view3d.set_mode", text="Editar").mode = 'EDIT'
                row.operator("view3d.set_mode", text="Esculpir").mode = 'SCULPT'
        else:
            layout.label(text="Selecione um objeto!", icon='PAUSE')

        if wm.joystick_shift:
            layout.label(text="Modo SHIFT Ativo", icon='PAUSE')
        else:
            layout.label(text="Modo Normal", icon='PAUSE')

        layout.separator()
        layout.operator("view3d.reset_viewport", icon='PAUSE')

        layout.separator()
        layout.separator()

        box = layout.box()
        box.label(text="Controle por Voz", icon='PAUSE')
        
        if google_client:
            box.label(text="Google Cloud: Ativo", icon='PAUSE')
        #else:
        #    box.label(text="Google Cloud: Inativo", icon='PAUSE')
        
        if is_listening:
            box.label(text="Status: Ouvindo...", icon='PAUSE')
        else:
            box.label(text="Status: Pronto", icon='PAUSE')
            
        box.label(text="Comandos disponíveis:")
        box.label(text="- Cubo, Esfera")
        box.label(text="- Frente, Render")
        box.label(text="- Esquerda, Direita")
        
        box.separator()
        box.label(text=f"Último comando:", icon='PAUSE')
        box.label(text=f"'{wm.last_voice_command}'", icon='PAUSE')
        
        #box.separator()
        #box.operator("view3d.test_microphone", icon='PAUSE')

classes = [
    VIEW3D_MT_JoystickPieMenu,
    VIEW3D_OT_JoystickNavigation,
    VIEW3D_OT_StartJoystickNavigation,
    VIEW3D_OT_StopJoystickNavigation,
    VIEW3D_OT_SetMode,
    VIEW3D_OT_ResetViewport,
    VIEW3D_OT_TestMicrophone,
    VIEW3D_PT_JoystickPanel,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.WindowManager.last_voice_command = StringProperty(
        name="Último Comando",
        default="Nenhum comando ainda"
    )

    bpy.types.WindowManager.joystick_mode = EnumProperty(
        name="Modo de Navegação",
        items=[
            ('FREE', "Livre", "Navegação livre da viewport"),
            ('ORBIT', "Orbital", "Orbitar em torno do objeto"),
            ('ROTATE_X', "Rotacionar X", "Rotacionar objeto no eixo X"),
            ('ROTATE_Y', "Rotacionar Y", "Rotacionar objeto no eixo Y")
        ],
        default='FREE'
    )
    
    bpy.types.WindowManager.joystick_target = PointerProperty(
        name="Objeto Alvo",
        type=bpy.types.Object
    )
    
    bpy.types.WindowManager.joystick_sensitivity = FloatProperty(
        name="Sensibilidade",
        min=0.01, max=2.0,
        default=0.2
    )
    
    bpy.types.WindowManager.joystick_shift = BoolProperty(
        name="Shift Ativo",
        default=False
    )
    
    bpy.types.WindowManager.joystick_orbit_speed = FloatProperty(
        name="Velocidade Orbital",
        min=0.1, max=3.0,
        default=1.0
    )

    global stop_voice_thread
    stop_voice_thread = False
    
    threading.Thread(target=udp_server_thread, daemon=True).start()
    threading.Thread(target=voice_capture_thread, daemon=True).start()

def unregister():
    global stop_voice_thread
    stop_voice_thread = True

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    
    del bpy.types.WindowManager.joystick_mode
    del bpy.types.WindowManager.joystick_target
    del bpy.types.WindowManager.joystick_sensitivity
    del bpy.types.WindowManager.joystick_shift
    del bpy.types.WindowManager.joystick_orbit_speed

if __name__ == "__main__":
    register()
