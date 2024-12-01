'''проходит по всем видео И ИЗОБРАЖЕНИЯМ в input_directory и конвертирует их в webm-ки подходящие для видео-стикеров в телеге (в output_directory)

важно что видосы и гифки УСКОРЯЮТСЯ если это нужно а не обрезаются
прозрачность у png сохраняется

Video Requirements for Telegram Video Stickers:
• Duration must not exceed 3 seconds.
• For stickers, one side must be 512 pixels in size – the other side can be 512 pixels or less.
• Video must have no audio stream.
• Video must be in .WEBM format, up to 30 FPS.
• Video must be encoded with the VP9 codec.
• Video size should not exceed 256 KB after encoding.
• ..от себя добавлю что и палитра цветов должна быть определенная и профиль VP9 должен быть нулевой но они бля об этом не информируют'''


import os
import subprocess


########################### ТО ЧТО МОЖНО МЕНЯТЬ ######################################

input_directory = '/Users/chumbulev/Downloads'    # ПАПКА с исходниками
output_directory = ''    # ПАПКА куда экспортировать ('' -> экспортируем рядом с исходниками) (может не существовать)

MAX_SIDE = 512  # px
MAX_DURATION = 2.7  # sec
MAX_SIZE = 1000 * 250  # 250KB    походу файндер умножает на 1000 а не на 1024 так что и мы будем также делать.
MAX_FPS = 24  # fps
TARGET_FORMAT = 'webm'
TARGET_CODEC = 'vp9'

######################################################################################


def get_file_duration(file_path):
    '''возвращает длительность файла file_path (средствами ffprobe) (в секундах, float)'''

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


def get_file_fps(file_path):
    '''Возвращает fps видеофайла file_path в float (средствами ffprobe)'''
    result = subprocess.run(
        [
            "ffprobe",
            "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=r_frame_rate",
            "-of", "default=noprint_wrappers=1:nokey=1",
            file_path
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    # Получаем строку с дробью (например, "30000/1001") и вычисляем ее значение float
    fps_str = result.stdout.strip()
    num, denom = map(int, fps_str.split('/'))
    return num / denom


def get_file_kbps(file_path):
    '''Возвращает битрейт видеофайла file_path в килобитах в секунду (float) с использованием ffprobe'''
    result = subprocess.run(
        [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=bit_rate",
            "-of", "default=noprint_wrappers=1:nokey=1",
            file_path
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    # Получаем строку с битрейтом в битах (например, "128000") и преобразуем в float, переводя в килобиты
    bitrate_bps = int(result.stdout.strip())
    return bitrate_bps / 1000  # Перевод в килобит/с


def get_file_KB(file_path):
    '''возвращает строку количества KB вида '12 345.678' (это пример 12MB)'''

    bytes_size = os.path.getsize(file_path)

    kb_size = bytes_size / 1000 # файндер походу считает деля на 1000 а не на 1024 так что и я буду.

    # Форматирование в строку с разделением тысяч и тремя знаками после запятой
    kb_formatted = f"{kb_size:,.3f}".replace(",", " ")

    return kb_formatted


def get_output_file_path(input_file_path, output_dir):
    '''возвращает строку вида "outputdir/IMG_19700101_010101_jpg.webm"'''
    file_name = os.path.splitext(os.path.basename(input_file_path))[0]  # 'IMG_19700101_010101'
    file_orig_extension = os.path.splitext(os.path.basename(input_file_path))[1][1::]  # 'jpg'
    return os.path.join(output_dir, file_name + '_' + file_orig_extension + '.' + TARGET_FORMAT)  # 'output_dir/IMG_19700101_010101_jpg.webm'


def convert_webp_to_jpg(file_path):
    '''
    Возвращает путь к новому файлу .jpg или -1 в случае ошибки конвертации
    '''
    try:
        # Получаем директорию и имя файла без расширения
        directory, file_name = os.path.split(file_path)
        # webp_name, _ = os.path.splitext(file_name)
        jpg_name = 'temp_' + os.path.splitext(file_name)[0] + '.jpg'

        # Формируем путь для нового файла .jpg
        jpg_file_path = os.path.join(directory, jpg_name)

        # Команда FFmpeg для конвертации .webp в .jpg
        result = subprocess.run(
            [
                "ffmpeg",
                "-y",  # Перезаписывать выходной файл без запроса
                "-i", file_path,  # Входной файл
                jpg_file_path  # Выходной файл
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        # Проверяем успешность конвертации
        if result.returncode == 0:
            return jpg_file_path
        else:
            raise ValueError(f"⚠️ конвертация завершилась с кодом {result.returncode}")
    except Exception:
        print("⚠️ ошибка при конвертации из .webp в .jpg")


def process_file(input_file_path, output_file_path):
    '''Обрабатывает видео: масштабирование, ускорение, удаление аудио, конвертация в webm'''
    try:
        orig_extension = os.path.splitext(os.path.basename(input_file_path))[1]  #  -->  '.jpg'

        # инициализируем начальные длительность, fps и битрейт файла
        file_duration = get_file_duration(input_file_path)

        if orig_extension in ('.gif', '.mp4', '.mov', '.avi', '.mkv'):
            fps = min(round(get_file_fps(input_file_path)), MAX_FPS)  # (нужно только для видосов и гифов) берет fps ориг файла если он меньше MAX_FPS, иначен берет MAX_FPS
        else:
            fps = -1

        if orig_extension in ('.gif', '.mp4', '.mov', '.avi', '.mkv'):
            bitrate = min(round(get_file_kbps(input_file_path)), 1000)  # берет kbps ориг видоса или гифки если он меньше 1000, иначен берет 1000
        elif orig_extension in ('.jpg', '.jpeg', '.png', '.webp'):
            bitrate = min(round(get_file_kbps(input_file_path)), 10000)  # берет kbps ориг пикчи если он меньше 10 000, иначен берет 10 000
        else:
            bitrate = -1

        # цикл: последовательно конвертация и уменьшение размера
        while True:
            if orig_extension in ('.gif', '.mp4', '.mov', '.avi', '.mkv'):
                if file_duration > MAX_DURATION:  # если видео/гифка длиннее 3 секунд, ускоряем
                    speed_factor = file_duration / MAX_DURATION
                    terminal_command = f'''ffmpeg -y -i {input_file_path} -filter_complex "[0:v]format=yuva420p,fps={fps},scale='if(gte(iw,ih),{MAX_SIDE},-1)':'if(gte(iw,ih),-1,{MAX_SIDE})',setpts=PTS/{speed_factor}" -c:v libvpx-{TARGET_CODEC} -b:v {bitrate}k -pix_fmt yuva420p -an -t {MAX_DURATION} {output_file_path}'''
                else:  # если видео/гифка не требует ускорения
                    terminal_command = f'''ffmpeg -y -i {input_file_path} -filter_complex "[0:v]format=yuva420p,fps={fps},scale='if(gte(iw,ih),{MAX_SIDE},-1)':'if(gte(iw,ih),-1,{MAX_SIDE})'" -c:v libvpx-{TARGET_CODEC} -b:v {bitrate}k -pix_fmt yuva420p -an -t {file_duration} {output_file_path}'''
            else: # для изображений
                terminal_command = f'''ffmpeg -y -i {input_file_path} -filter_complex "[0:v]format=yuva420p,          scale='if(gte(iw,ih),{MAX_SIDE},-1)':'if(gte(iw,ih),-1,{MAX_SIDE})'" -c:v libvpx-{TARGET_CODEC} -b:v {bitrate}k -pix_fmt yuva420p -an -t {file_duration} {output_file_path}'''

            subprocess.run(terminal_command, shell=True, capture_output=True, text=True)

            # Проверяем размер файла
            if os.path.getsize(output_file_path) <= MAX_SIZE:
                break
            else:
                # Уменьшаем FPS и битрейт
                fps = max(5, fps - 2)  # Минимальный FPS 5
                bitrate = max(100, bitrate - 100)  # Минимальный битрейт 100 kbit/s

                # если достигли минимальных возможных значений fps и битрейта:
                if fps == 5 and bitrate == 100:
                    print(f'⚠️ достигнуты минимально возможные fps и битрейт и размер файла все равно > {MAX_SIZE}')
                    break

    except Exception as e:
        print(f"⚠️ ошибка при обработке файла {input_file_path}: {e}")



################################################ MAIN ######################################################


def main(input_dir, output_dir):
    if output_dir == '':     # если output_dir пустая строка то экпортируем в директорию исходников
        output_dir = input_dir
    elif not os.path.exists(output_dir):   # если же output_dir указана явно но такой папки не существует то создаем ее
        os.makedirs(output_dir)

    files_count = 0  # счетчик для вывода в консоль

    # Проходим по всем файлам в директории
    for filename in os.listdir(input_dir):
        input_file_path = os.path.join(input_dir, filename)
        orig_extension = os.path.splitext(os.path.basename(input_file_path))[1]  # -->  '.jpg'
        if orig_extension in ('.mp4', '.mov', '.avi', '.mkv', '.gif', '.jpg', '.jpeg', '.png', '.webp'):
            files_count += 1

            output_file_path = get_output_file_path(input_file_path, output_dir)

            # ffmpeg не конвертирует webp нормально в webm поэтому приходится предварительно конвертировать его во временный файл jpg
            if orig_extension == '.webp':
                try:
                    input_file_path = convert_webp_to_jpg(input_file_path)
                except Exception:
                    print(Exception)

            print(f"{files_count}. {filename}:")

            process_file(input_file_path, output_file_path)

            # вывод строки вида '7.82 sec  -->  2.99 sec' :
            print(' ' * (len(str(files_count)) + 1), f'{round(get_file_duration(input_file_path), 2)} sec  -->  {round(get_file_duration(output_file_path), 2)} sec')
            # вывод строки вида '24.98 fps  -->  18.00 fps' :
            print(' ' * (len(str(files_count)) + 1), f'{round(get_file_fps(input_file_path), 2)} fps  -->  {round(get_file_fps(output_file_path), 2)} fps')
            # вывод строки вида '2828.147 kbit/s  -->  735.761 kbit/s' :
            print(' ' * (len(str(files_count)) + 1), f'{round(get_file_kbps(input_file_path))} kbit/s  -->  {round(get_file_kbps(output_file_path))} kbit/s')
            # вывод строки вида '12 345.678 KB  -->  249.12 KB'
            print(' ' * (len(str(files_count)) + 1), f'{get_file_KB(input_file_path)} KB  -->  {get_file_KB(output_file_path)} KB')

if __name__ == '__main__':
    main(input_directory, output_directory)