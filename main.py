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
cam_distance = 25.0
mouse_sensitivity = 0.2
zoom_speed = 1.0


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


# ======================
# Programa principal
# ======================
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
    tex_sun = load_texture("sol.jpg")
    tex_earth = load_texture("earth.jpg")
    tex_norm = load_texture("normal_map_earth.tif")
    tex_mars = load_texture("8k_mars.jpg")
    tex_moon = load_texture("8k_moon.jpg")

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

    # ::INFO - Dá zoom
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

        # === Calcula posição da luz (Sol) em view space ===
        light_world = [0.0, 0.0, 0.0, 1.0]
        mv_view = glGetDoublev(GL_MODELVIEW_MATRIX)
        light_view = [
            mv_view[0][0]*light_world[0] + mv_view[0][1]*light_world[1] + mv_view[0][2]*light_world[2] + mv_view[0][3],
            mv_view[1][0]*light_world[0] + mv_view[1][1]*light_world[1] + mv_view[1][2]*light_world[2] + mv_view[1][3],
            mv_view[2][0]*light_world[0] + mv_view[2][1]*light_world[1] + mv_view[2][2]*light_world[2] + mv_view[2][3]
        ]

        # 🌞 Sol (iluminador)
        glDisable(GL_LIGHTING)
        if tex_sun:
            glBindTexture(GL_TEXTURE_2D, tex_sun)
            q = gluNewQuadric()
            gluQuadricTexture(q, GL_TRUE)
            gluSphere(q, 2.0, 64, 64)
        else:
            draw_sphere_color(2.0, (1, 1, 0))

        # 🌍 Terra (shader + normal map)
        glPushMatrix()
        glRotatef(angle_earth, 0, 1, 0)
        glTranslatef(8.0, 0.0, 0.0)
        glRotatef(earth_self, 0, 1, 0)

        glUseProgram(program)
        glUniform1i(loc_diffuse, 0)
        glUniform1i(loc_normalmap, 1)
        glUniform3f(loc_lightpos, *light_view)

        glActiveTexture(GL_TEXTURE0)
        glBindTexture(GL_TEXTURE_2D, tex_earth)
        glActiveTexture(GL_TEXTURE1)
        glBindTexture(GL_TEXTURE_2D, tex_norm)

        q = gluNewQuadric()
        gluQuadricTexture(q, GL_TRUE)
        gluSphere(q, 0.8, 64, 64)

        glUseProgram(0)
        glActiveTexture(GL_TEXTURE1)
        glBindTexture(GL_TEXTURE_2D, 0)
        glActiveTexture(GL_TEXTURE0)
        glBindTexture(GL_TEXTURE_2D, 0)
        glPopMatrix()

        # 🌕 Lua
        glPushMatrix()
        glRotatef(angle_earth, 0, 1, 0)
        glTranslatef(8.0, 0.0, 0.0)
        glRotatef(angle_moon, 0, 1, 0)
        glTranslatef(2.0, 0.0, 0.0)
        if tex_moon:
            glBindTexture(GL_TEXTURE_2D, tex_moon)
            q = gluNewQuadric()
            gluQuadricTexture(q, GL_TRUE)
            gluSphere(q, 0.3, 64, 64)
        else:
            draw_sphere_color(0.3, (0.8, 0.8, 0.8))
        glPopMatrix()

        # 🔴 Marte
        glPushMatrix()
        glRotatef(angle_mars, 0, 1, 0)
        glTranslatef(13.0, 0.0, 0.0)
        if tex_mars:
            glBindTexture(GL_TEXTURE_2D, tex_mars)
            q = gluNewQuadric()
            gluQuadricTexture(q, GL_TRUE)
            gluSphere(q, 0.6, 64, 64)
        else:
            draw_sphere_color(0.6, (1.0, 0.3, 0.0))
        glPopMatrix()

        # === Animações ===
        angle_earth += 0.5
        earth_self += 1.0
        angle_moon += 2.0
        angle_mars += 0.3

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()


if __name__ == "__main__":
    main()
