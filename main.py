import pygame
from pygame.locals import *
from OpenGL.GL import *
from OpenGL.GLU import *
import math


# ======================
# Variáveis globais
# ======================
angle_earth = 0.0
angle_moon = 0.0
angle_mars = 0.0
earth_self = 0.0

cam_angle_x = 10.0
cam_angle_y = 180.0
cam_distance = 100.0
mouse_sensitivity = 0.2
zoom_speed = 2.0


# ======================
# Utilidades
# ======================
def load_texture(path):
    try:
        surf = pygame.image.load(path)
    except Exception as e:
        print(f"❌ Erro ao carregar textura '{path}': {e}")
        return None
    surf = pygame.transform.flip(surf, False, True)
    data = pygame.image.tostring(surf, "RGB", 1)
    w, h = surf.get_rect().size

    tex = glGenTextures(1)
    glBindTexture(GL_TEXTURE_2D, tex)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_REPEAT)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_REPEAT)
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, w, h, 0, GL_RGB, GL_UNSIGNED_BYTE, data)
    print(f"✅ Textura carregada: {path} ({w}x{h})")
    return tex


def draw_sphere_color(radius, color):
    glColor3fv(color)
    q = gluNewQuadric()
    gluSphere(q, radius, 32, 32)


def set_camera():
    x = cam_distance * math.sin(math.radians(cam_angle_y)) * math.cos(math.radians(cam_angle_x))
    y = cam_distance * math.sin(math.radians(cam_angle_x))
    z = cam_distance * math.cos(math.radians(cam_angle_y)) * math.cos(math.radians(cam_angle_x))
    glMatrixMode(GL_MODELVIEW)
    glLoadIdentity()
    gluLookAt(x, y, z, 0, 0, 0, 0, 1, 0)


# ======================
# Shaders (GLSL)
# ======================
VERT_SRC = """
#version 120
varying vec3 vPosV;
varying vec2 vUV;
void main() {
    vec4 posV = gl_ModelViewMatrix * gl_Vertex;
    vPosV = posV.xyz;
    vUV   = gl_MultiTexCoord0.st;
    gl_Position = gl_ModelViewProjectionMatrix * gl_Vertex;
}
"""

FRAG_SRC = """
#version 120
uniform sampler2D uDiffuse;
uniform sampler2D uNormalMap;
uniform vec3 uLightPosV;

varying vec3 vPosV;
varying vec2 vUV;

void main() {
    vec3 base = texture2D(uDiffuse, vUV).rgb;

    // Normais geométricas e tangente-space
    vec3 dp1 = dFdx(vPosV);
    vec3 dp2 = dFdy(vPosV);
    vec2 duv1 = dFdx(vUV);
    vec2 duv2 = dFdy(vUV);

    vec3 Ngeo = normalize(cross(dp1, dp2));
    vec3 T = normalize(dp1 * duv2.y - dp2 * duv1.y);
    vec3 B = normalize(-dp1 * duv2.x + dp2 * duv1.x);

    vec3 nTex = texture2D(uNormalMap, vUV).rgb * 2.0 - 1.0;
    mat3 TBN = mat3(T, B, Ngeo);
    vec3 N = normalize(TBN * nTex);

    // Luz direcional a partir do Sol
    vec3 L = normalize(uLightPosV - vPosV);
    float diff = max(dot(N, L), 0.0);

    // Simula sombra: lado oposto fica escuro
    vec3 ambient = 0.05 * base;
    vec3 color = ambient + base * diff;

    gl_FragColor = vec4(color, 1.0);
}
"""


def compile_shader(src, stype):
    sid = glCreateShader(stype)
    glShaderSource(sid, src)
    glCompileShader(sid)
    if not glGetShaderiv(sid, GL_COMPILE_STATUS):
        raise RuntimeError(glGetShaderInfoLog(sid).decode())
    return sid


def create_program(vsrc, fsrc):
    vs = compile_shader(vsrc, GL_VERTEX_SHADER)
    fs = compile_shader(fsrc, GL_FRAGMENT_SHADER)
    pid = glCreateProgram()
    glAttachShader(pid, vs)
    glAttachShader(pid, fs)
    glLinkProgram(pid)
    if not glGetProgramiv(pid, GL_LINK_STATUS):
        raise RuntimeError(glGetProgramInfoLog(pid).decode())
    glDeleteShader(vs)
    glDeleteShader(fs)
    return pid


def draw_skybox(texture_id):
    """Desenha uma esfera invertida com textura de estrelas ao fundo."""
    glPushMatrix()
    glDisable(GL_LIGHTING)
    glDisable(GL_DEPTH_TEST)
    glDisable(GL_CULL_FACE)
    glEnable(GL_TEXTURE_2D)

    glBindTexture(GL_TEXTURE_2D, texture_id)
    q = gluNewQuadric()
    gluQuadricTexture(q, GL_TRUE)
    gluQuadricOrientation(q, GLU_INSIDE)  # Inverte a esfera (olhar de dentro)
    gluSphere(q, 200.0, 64, 64)  # Raio bem grande
    
    glEnable(GL_DEPTH_TEST)
    glEnable(GL_CULL_FACE)
    glEnable(GL_LIGHTING)
    glPopMatrix()


def draw_orbit(radius, color=(0.3, 0.3, 0.3), segments=128):
    """Desenha uma linha circular representando a órbita de um planeta."""
    was_program = glGetIntegerv(GL_CURRENT_PROGRAM)
    tex_enabled = glIsEnabled(GL_TEXTURE_2D)

    glUseProgram(0)
    if tex_enabled:
        glDisable(GL_TEXTURE_2D)

    glColor3fv(color)
    glBegin(GL_LINE_LOOP)
    for i in range(segments):
        a = 2.0 * math.pi * i / segments
        x = math.cos(a) * radius
        z = math.sin(a) * radius
        glVertex3f(x, 0.0, z)
    glEnd()

    glColor3f(1.0, 1.0, 1.0)

    if tex_enabled:
        glEnable(GL_TEXTURE_2D)
    if was_program:
        glUseProgram(was_program)



def main():
    global angle_earth, angle_mars, angle_moon, earth_self
    global cam_angle_x, cam_angle_y, cam_distance

    pygame.init()
    size = (900, 700)
    pygame.display.set_mode(size, DOUBLEBUF | OPENGL)
    pygame.display.set_caption("Sistema Solar 3D - PyOpenGL + Normal Map + Luz Direcional")

    # OpenGL setup
    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    gluPerspective(45.0, size[0] / float(size[1]), 0.1, 500.0)
    glMatrixMode(GL_MODELVIEW)
    glEnable(GL_DEPTH_TEST)
    glEnable(GL_TEXTURE_2D)
    glClearColor(0.0, 0.0, 0.0, 1.0)

    # Texturas
    tex_sun = load_texture("textures/sol.jpg")
    tex_earth = load_texture("textures/earth.jpg")
    tex_norm = load_texture("textures/normal_map_earth.tif")
    tex_moon = load_texture("textures/8k_moon.jpg")
    tex_mars = load_texture("textures/8k_mars.jpg")
    tex_mercury = load_texture("textures/8k_mercury.jpg")
    tex_venus = load_texture("textures/8k_venus_surface.jpg")
    tex_jupiter = load_texture("textures/8k_jupiter.jpg")
    tex_saturn = load_texture("textures/8k_saturn.jpg")
    tex_uranus = load_texture("textures/2k_uranus.jpg")
    tex_neptune = load_texture("textures/2k_neptune.jpg")
    tex_stars = load_texture("textures/8k_stars_milky_way.jpg")

    # Shader
    program = create_program(VERT_SRC, FRAG_SRC)
    loc_diffuse = glGetUniformLocation(program, "uDiffuse")
    loc_normalmap = glGetUniformLocation(program, "uNormalMap")
    loc_lightpos = glGetUniformLocation(program, "uLightPosV")

    pygame.event.set_grab(True)
    pygame.mouse.set_visible(False)
    last_mouse = pygame.mouse.get_pos()

    clock = pygame.time.Clock()
    running = True

    # Ângulos individuais
    angles = {
        "mercury": 0.0,
        "venus": 0.0,
        "earth": 0.0,
        "mars": 0.0,
        "jupiter": 0.0,
        "saturn": 0.0,
        "uranus": 0.0,
        "neptune": 0.0,
        "moon": 0.0
    }
    self_rot = 0.0

    # Dados dos planetas (raio de órbita, tamanho, velocidade orbital, textura)
    planets = [
        ("mercury", 3.5, 0.25, 1.6, tex_mercury),
        ("venus", 5.5, 0.45, 1.2, tex_venus),
        ("earth", 8.0, 0.8, 0.8, tex_earth),
        ("mars", 13.0, 0.6, 0.5, tex_mars),
        ("jupiter", 20.0, 1.5, 0.3, tex_jupiter),
        ("saturn", 26.0, 1.2, 0.25, tex_saturn),
        ("uranus", 31.0, 0.9, 0.2, tex_uranus),
        ("neptune", 36.0, 0.85, 0.18, tex_neptune)
    ]

    # Loop principal
    while running:
        for e in pygame.event.get():
            if e.type == QUIT:
                running = False
            if e.type == MOUSEBUTTONDOWN:
                if e.button == 4: cam_distance = max(5.0, cam_distance - zoom_speed)
                if e.button == 5: cam_distance = min(100.0, cam_distance + zoom_speed)

        # === Câmera ===
        mx, my = pygame.mouse.get_pos()
        dx, dy = mx - last_mouse[0], my - last_mouse[1]
        last_mouse = (mx, my)
        cam_angle_y += dx * mouse_sensitivity
        cam_angle_x = max(-89.0, min(89.0, cam_angle_x - dy * mouse_sensitivity))

        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        set_camera()

        if tex_stars:
            draw_skybox(tex_stars)

        # === Luz (Sol) ===
        light_world = [0.0, 0.0, 0.0, 1.0]
        mv_view = glGetDoublev(GL_MODELVIEW_MATRIX)
        light_view = [
            mv_view[0][0]*light_world[0] + mv_view[0][1]*light_world[1] + mv_view[0][2]*light_world[2] + mv_view[0][3],
            mv_view[1][0]*light_world[0] + mv_view[1][1]*light_world[1] + mv_view[1][2]*light_world[2] + mv_view[1][3],
            mv_view[2][0]*light_world[0] + mv_view[2][1]*light_world[1] + mv_view[2][2]*light_world[2] + mv_view[2][3]
        ]

        # 🌞 Sol
        glDisable(GL_LIGHTING)
        if tex_sun:
            glBindTexture(GL_TEXTURE_2D, tex_sun)
            q = gluNewQuadric()
            gluQuadricTexture(q, GL_TRUE)
            gluSphere(q, 2.0, 64, 64)
        else:
            draw_sphere_color(2.0, (1, 1, 0))


        # 🌀 ÓRBITAS DOS PLANETAS
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        for name, orbit_radius, radius, orbit_speed, tex in planets:
            draw_orbit(orbit_radius, color=(0.6, 0.6, 0.6))  # Cor neutra e discreta
        glDisable(GL_BLEND)

        # 🪐 Planetas
        for name, orbit_radius, radius, orbit_speed, tex in planets:
            glPushMatrix()
            angles[name] += orbit_speed
            glRotatef(angles[name], 0, 1, 0)
            glTranslatef(orbit_radius, 0.0, 0.0)
            if name == "earth":
                glRotatef(self_rot, 0, 1, 0)
                glUseProgram(program)
                glUniform1i(loc_diffuse, 0)
                glUniform1i(loc_normalmap, 1)
                glUniform3f(loc_lightpos, *light_view)
                glActiveTexture(GL_TEXTURE0)
                glBindTexture(GL_TEXTURE_2D, tex)
                glActiveTexture(GL_TEXTURE1)
                glBindTexture(GL_TEXTURE_2D, tex_norm)
                q = gluNewQuadric()
                gluQuadricTexture(q, GL_TRUE)
                gluSphere(q, radius, 64, 64)
                glUseProgram(0)
                glActiveTexture(GL_TEXTURE1)
                glBindTexture(GL_TEXTURE_2D, 0)
                glActiveTexture(GL_TEXTURE0)
                glBindTexture(GL_TEXTURE_2D, 0)
            else:
                if tex:
                    glColor3f(1.0, 1.0, 1.0)
                    glTexEnvi(GL_TEXTURE_ENV, GL_TEXTURE_ENV_MODE, GL_REPLACE)

                    glBindTexture(GL_TEXTURE_2D, tex)
                    q = gluNewQuadric()
                    gluQuadricTexture(q, GL_TRUE)
                    gluSphere(q, radius, 64, 64)

                    glTexEnvi(GL_TEXTURE_ENV, GL_TEXTURE_ENV_MODE, GL_MODULATE)
                else:
                    draw_sphere_color(radius, (0.6, 0.6, 0.6))

            glPopMatrix()

        # 🌕 Lua orbitando a Terra
        glPushMatrix()
        glRotatef(angles["earth"], 0, 1, 0)
        glTranslatef(8.0, 0.0, 0.0)
        angles["moon"] += 2.0
        glRotatef(angles["moon"], 0, 1, 0)
        glTranslatef(1.5, 0.0, 0.0)
        if tex_moon:
            glBindTexture(GL_TEXTURE_2D, tex_moon)
            q = gluNewQuadric()
            gluQuadricTexture(q, GL_TRUE)
            gluSphere(q, 0.3, 64, 64)
        else:
            draw_sphere_color(0.3, (0.8, 0.8, 0.8))
        glPopMatrix()

        # === Rotação própria da Terra ===
        self_rot += 1.0

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()

    


if __name__ == "__main__":
    main()
