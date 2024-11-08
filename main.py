'''проходит по всем видео И ИЗОБРАЖЕНИЯМ в input_directory и конвертирует их в webm-ки подходящие для видео-стикеров в телеге (в output_directory)

важно что видосы и гифки УСКОРЯЮТСЯ если это нужно а не обрезаются

Video Requirements for Telegram Video Stickers:
• Duration must not exceed 3 seconds.
• For stickers, one side must be 512 pixels in size – the other side can be 512 pixels or less.
• Video must have no audio stream.
• Video must be in .WEBM format, up to 30 FPS.
• Video must be encoded with the VP9 codec.
• Video size should not exceed 256 KB after encoding.
• ..от себя добавлю что и палитра цветов должна быть определенная и профиль VP9 должен быть нулевой но они бля об этом не информируют'''


import os
# для предварительными манипуляциями с видосами:
import moviepy.editor as mp # весь доступ к ffmpeg (для видосов) -- через этого малыша
# для :
import subprocess # для выполнения терминальной команды ffmpeg для изображений
# от бага с ANTIALIAS<->LANCZOS в PIL.Image:
from PIL import Image
from numpy  import array as nparray


########################### ТО ЧТО МОЖНО МЕНЯТЬ ######################################

input_directory = '/Users/chumbulev/Pictures/✂️Screenshots'    # ПАПКА с исходниками
output_directory = ''    # ПАПКА куда экспортировать ('' -> экспортируем рядом с исходниками) (может не существовать)

MAX_SIDE = 512  # px
MAX_DURATION = 2.7  # sec
MAX_SIZE = 250 * 1024  # 250KB
MAX_FPS = 24  # fps
TARGET_FORMAT = 'webm'
TARGET_CODEC = 'vp9'

######################################################################################


def get_file_duration(file_path):
    '''возвращает длительность файла file_path (средствами ffprobe) (в секундах)'''
    result = subprocess.run(
        [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            file_path
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    # Преобразуем результат в число с плавающей точкой
    return float(result.stdout.strip())


def resize_video(clip, max_side):
    '''возвращает clip отмасштабированный так что бОльшая сторона = 512pxl с использованием алгоритма LANCZOS'''

    def resize_frame(frame):
        img = Image.fromarray(frame)
        w, h = img.size
        if max(w, h) > max_side:
            scale_factor = max_side / max(w, h)
            new_size = (int(w * scale_factor), int(h * scale_factor))
            # Применение LANCZOS для масштабирования
            img = img.resize(new_size, Image.LANCZOS)
        return nparray(img)

    # Применяем функцию resize_frame к каждому кадру видео
    return clip.fl_image(resize_frame)


def adjust_video_duration(clip, max_duration):
    """возвращает clip, ускоренный если его длительность больше max_duration секунд"""
    if clip.duration > max_duration:
        speed_factor = clip.duration / max_duration
        return clip.fx(mp.vfx.speedx, speed_factor)
    return clip


def remove_audio_in_video(clip):
    """возвращает clip без аудиодорожки"""
    return clip.without_audio()


def convert_video_to_webm(input_path, output_path, fps, bitrate):
    """Конвертирует (средствами ffmpeg) файл input_path в файл output_path (VP9 Profile 0, цветовое пространство yuv420p) с переданными fps и bitrate
    ('.webm' уже является частью output_path)"""
    command = [
        'ffmpeg', '-y', '-i', input_path,
        '-c:v', TARGET_CODEC,
        '-b:v', f'{bitrate}k',
        '-r', str(fps),
        '-pix_fmt', 'yuv420p',  # Установка цветового пространства
        '-profile:v', '0',      # Установка VP9 Profile 0
        '-an',  # повторное даление аудио на всякий
        output_path
    ]
    subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def process_video(input_file_path, output_dir):
    '''1. предварительная подготовка видео (масштабирование, ускорение, удаление аудио)

    2. в цикле: convert_video_to_webm() и понижение фпс и битрейта. до достижения допустимого веса файла'''
    try:
        # Открываем видео
        clip = mp.VideoFileClip(input_file_path)

        # Изменяем размер видео
        clip = resize_video(clip, MAX_SIDE)

        # Ускоряем видео до 3 секунд, если требуется
        clip = adjust_video_duration(clip, MAX_DURATION)

        # Убираем аудиодорожку
        clip = remove_audio_in_video(clip)

        # Сохраняем промежуточное видео во временный файл
        temp_output_path = os.path.join(output_dir, "temp_video.mp4")
        clip.write_videofile(temp_output_path, codec='libx264', fps=MAX_FPS, verbose=False, logger=None)

        # Конвертация и контроль веса
        final_output_path = os.path.join(output_dir, os.path.splitext(os.path.basename(input_file_path))[0] + ".webm")
        fps = MAX_FPS
        bitrate = 1000  # начальный битрейт в kbit/s

        while True:
            # Пробуем конвертировать с текущими fps и битрейтом
            convert_video_to_webm(temp_output_path, final_output_path, fps, bitrate)

            # Проверяем размер файла
            if os.path.getsize(final_output_path) <= MAX_SIZE:
                break
            else:
                # Уменьшаем FPS и битрейт, если файл больше 256KB
                fps = max(5, fps - 5)  # Минимальный FPS 5
                bitrate = max(100, bitrate - 100)  # Минимальный битрейт 100 kbit/s

        # Удаляем временный файл
        os.remove(temp_output_path)

    except Exception as e:
        print(f"⚠️Ошибка при обработке видео {input_file_path}: {e}")


def process_gif(input_file_path, output_dir):
    '''берет пикчу input_file_path и конвертирует ее средствами ffmpeg в .webm в папке output_dir (vp9, 512pxl, палитра yuva420p, 25 fps).

    Duration ускоряется до MAX_DURATION если надо'''
    try:
        # получаеется  output_dir + / + имя исходника без расширения + .webm
        output_file_path = os.path.join(output_dir, os.path.splitext(os.path.basename(input_file_path))[0] + ".webm")

        gif_duration = get_file_duration(input_file_path)
        if gif_duration > MAX_DURATION:  # .gif дольше MAX_DURATION сек
            # терминальная команда ffmpeg которая: масштабирует input_file_path до 512pxl, УСКОРЯЕТ ДАННЫЙ GIF ДО MAX_DURATION СЕК, конвертирует в webm (vp9, палитра yuva420p учитывающая прозрачность) и создает файл output_file_path
            terminal_command = f'''ffmpeg -y -i {input_file_path} -filter_complex "[0:v]format=yuva420p,scale='if(gte(iw,ih),{MAX_SIDE},-1)':'if(gte(iw,ih),-1,{MAX_SIDE})',setpts=PTS/({gif_duration}/{MAX_DURATION})" -c:v libvpx-vp9 -pix_fmt yuva420p -t {MAX_DURATION} {output_file_path}'''
        else:  # .gif короче MAX_DURATION сек (либо равно)
            # терминальная команда ffmpeg которая масштабирует input_file_path до 512pxl, СОХРАНЯЕТ DURATION ДАННОГО GIF, конвертирует в webm (vp9, палитра yuva420p учитывающая прозрачность) и создает файл output_file_path
            terminal_command = f'''ffmpeg -y -i {input_file_path} -filter_complex "[0:v]format=yuva420p,scale='if(gte(iw,ih),{MAX_SIDE},-1)':'if(gte(iw,ih),-1,{MAX_SIDE})'" -c:v libvpx-vp9 -pix_fmt yuva420p -t {gif_duration} {output_file_path}'''

        subprocess.run(terminal_command, shell=True, capture_output=True, text=True)

    except Exception as e:
        print(f"⚠️Ошибка при обработке изображения {input_file_path}: {e}")


def process_static_image(input_file_path, output_dir):
    '''берет пикчу input_file_path и конвертирует ее средствами ffmpeg в .webm в папке output_dir (vp9, 512pxl, палитра yuva420p, 25 fps).
    Для обычных пикчей получается duration 4мс'''
    try:
        # получаеется  output_dir + / + имя исходника без расширения + .webm
        output_file_path = os.path.join(output_dir, os.path.splitext(os.path.basename(input_file_path))[0] + ".webm")

        terminal_command = f'''ffmpeg -y -i {input_file_path} -filter_complex "[0:v]format=yuva420p,scale='if(gte(iw,ih),{MAX_SIDE},-1)':'if(gte(iw,ih),-1,{MAX_SIDE})'" -c:v libvpx-vp9 -pix_fmt yuva420p -t 1 {output_file_path}'''

        subprocess.run(terminal_command, shell=True, capture_output=True, text=True)

    except Exception as e:
        print(f"⚠️Ошибка при обработке изображения {input_file_path}: {e}")


################################################ MAIN ######################################################


def main(input_dir, output_dir):
    if output_dir == '':     # если output_dir пустая строка то экпортируем в директорию исходников
        output_dir = input_dir
    elif not os.path.exists(output_dir):   # если же output_dir указана явно но такой папки не существует то создаем ее
        os.makedirs(output_dir)

    files_count = 0  # счетчик для вывода в консоль

    # Проходим по всем файлам в директории
    for filename in os.listdir(input_dir):
        file_path = os.path.join(input_dir, filename)
        if filename.endswith(('.mp4', '.mov', '.avi', '.mkv')):
            files_count += 1
            print(f"{files_count}. Видео {filename}:")

            process_video(file_path, output_dir) # полностью процесс конвертации и записи

            output_file_path = os.path.join(output_dir, os.path.splitext(os.path.basename(file_path))[0] + ".webm")  # output_dir + / + filename без раширения файла + .webm :
            print(' ' * (len(str(files_count)) + 1), f'{round(get_file_duration(file_path), 2)} sec  -->  {round(get_file_duration(output_file_path), 2)} sec') # выводится строка вида '7.82 sec  -->  2.99 sec'
        elif filename.endswith(('.gif')):
            files_count += 1
            print(f"{files_count}. Гифка {filename}:")

            process_gif(file_path, output_dir) # полностью процесс конвертации и записи

            output_file_path = os.path.join(output_dir, os.path.splitext(os.path.basename(file_path))[0] + ".webm")  # output_dir + / + filename без раширения файла + .webm :
            print(' ' * (len(str(files_count)) + 1), f'{round(get_file_duration(file_path), 2)} sec  -->  {round(get_file_duration(output_file_path), 2)} sec')  # выводится строка вида '7.82 sec  -->  2.99 sec'
        elif filename.endswith(('.jpg', '.jpeg', '.png', '.webp')):
            files_count += 1
            print(f"{files_count}. Изображение {filename}:")

            process_static_image(file_path, output_dir) # полностью процесс конвертации и записи

            print(' ' * (len(str(files_count)) + 1), '0.00 sec  -->  0.04 sec')


if __name__ == '__main__':
    main(input_directory, output_directory)