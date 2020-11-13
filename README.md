# M3u8Downloader
m3u8视频下载工具

采用多线程的方式进行m3u8格式的视频下载，并且合成mp4。默认采用ffmpeg进行合成(需要安装ffmepg),也可以直接支持流格式合并，直接设置--ffmpeg=False
使用帮助如下：

    python m3u8Downloader.py -h
    usage: m3u8Downloader.py [-h] -u URL [-o OUTPUT] [-t THREAD] [--ffmpeg]

    download video from m3u8

    optional arguments:
    -h, --help            show this help message and exit
    -u URL, --url URL     m3u8 url
    -o OUTPUT, --output OUTPUT
                        ouput video name, defult output.mp4
    -t THREAD, --thread THREAD
                        thread num, default 20
    --ffmpeg              use ffmpeg merge the ts file