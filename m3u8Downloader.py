import time
import os,shutil
import re
import random
import argparse
import requests
from retrying import retry
from Crypto.Cipher import AES
import threading
from concurrent.futures import ThreadPoolExecutor, wait, ALL_COMPLETED, as_completed # 线程池，进程池
from collections import Counter
from urllib.parse import urlparse,parse_qs

user_agent_list = [
    'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36 ',
    'Mozilla/5.0 (Windows NT 5.1; U; en; rv:1.8.1) Gecko/20061208 Firefox/2.0.0 Opera 9.50',
    'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:34.0) Gecko/20100101 Firefox/34.0',
    'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/534.57.2 (KHTML, like Gecko) Version/5.1.7 Safari/534.57.2',
    'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.71 Safari/537.36',
    'Mozilla/5.0 (Windows NT 6.1; WOW64; Trident/7.0; rv:11.0) like Gecko',
    'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/536.11 (KHTML, like Gecko) Chrome/20.0.1132.11 TaoBrow ser/2.0 Safari/536.11',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/71.0.3578.98 Safari/537.36'
]
header={'User-Agent': random.choice(user_agent_list)}
class M3u8Downloader:
    def __init__(self, url, poolSize=20, output =None, ffmpegFlag=True):
        self.url = url
        self.keyInfo ={}
        self.extInfo ={}
        self.key = None        
        self.tsList =[]
        self.poolSize = poolSize
        self.workDir = './tmp'
        self.output = output
        self.ffmpegFlag = ffmpegFlag

    def is_http(self, link):
        result = re.match(r'http[s]?', link, re.IGNORECASE)
        if result:
            return True
        return False
    def get_m3u8_info(self):
        '''
        m3u8格式
        #EXTM3U
        #EXT-X-VERSION:3
        #EXT-X-TARGETDURATION:10
        #EXT-X-MEDIA-SEQUENCE:0

        #EXT-X-KEY:METHOD=AES-128,URI="key.key",IV=0x12345（可能有）
        #EXTINF:10.000000,
        00000.ts

        youku 
        #EXTM3U
        #EXT-X-VERSION:3
        #EXT-X-TARGETDURATION:10
        #EXT-X-MEDIA-SEQUENCE:0
        #EXTINF:10.000000,
        #EXT-X-PRIVINF:FILESIZE=1104688
        https://valipl.cp31.ott.cibntv.net/67756D6080932713CFC02204E/03000600005FA51A662800EC81BA8F94282A19-C751-4101-A3AC-60BA39DCAEEF-00001.ts?ccode=0502&duration=5462&expire=18000&psid=9da79179b5e1fbfcda980369b0106b5d47d30&ups_client_netip=279a0c42&ups_ts=1604815942&ups_userid=&utid=g4TXF0qawiACAdrKgAsAE%2FTj&vid=XNDk0MTI2NzU4MA&sm=1&operate_type=0&dre=u37&si=73&eo=0&dst=1&iv=0&s=efbfbd147aefbfbdefbf&type=mp4hdv3&bc=2&hotvt=1&rid=20000000C04A53F7844C94AD5CA87365A04578CE02000000&vkey=Bb46fc27807038544c60bba7318f084ca
        #EXTINF:10.000000,
        #EXT-X-PRIVINF:FILESIZE=596148
        https://valipl.cp31.ott.cibntv.net/67756D6080932713CFC02204E/03000600005FA51A662800EC81BA8F94282A19-C751-4101-A3AC-60BA39DCAEEF-00002.ts?ccode=0502&duration=5462&expire=18000&psid=9da79179b5e1fbfcda980369b0106b5d47d30&ups_client_netip=279a0c42&ups_ts=1604815942&ups_userid=&utid=g4TXF0qawiACAdrKgAsAE%2FTj&vid=XNDk0MTI2NzU4MA&sm=1&operate_type=0&dre=u37&si=73&eo=0&dst=1&iv=0&s=efbfbd147aefbfbdefbf&type=mp4hdv3&bc=2&hotvt=1&rid=20000000C04A53F7844C94AD5CA87365A04578CE02000000&vkey=Bd2464f1afbe673464f56bedc4887ed45
        #EXTINF:10.000000,
        #EXT-X-PRIVINF:FILESIZE=665896
        '''
        content = requests.get(self.url, headers={'User-Agent': random.choice(user_agent_list)}).text
        if not re.match(r'#EXTM3U', content):
            print('the input url content is not m3u8')
            exit(1)
        result = re.split('#', content, flags=re.M)
        pattern =re.compile(r'EXT(.*):')
        #去除结尾的空白字符和逗号
        result = [re.sub(r',*\s$',"",item) for item in result if len(item) > 0] 
        keyList = [item[:item.find(':')] for item in result ] 
        keyDict={}
        for key in keyList:
            keyDict[key] = keyDict.get(key, 0) + 1

        for extItem in result:
            if pattern.match(extItem):
                extKey = extItem[:extItem.find(':')]
                extValue= extItem[extItem.find(':')+1:]
                if keyDict[extKey] > 1:
                    if not extKey in self.extInfo.keys():
                        self.extInfo[extKey]=[]
                    self.extInfo[extKey].append(extValue)
                else:
                    self.extInfo[extKey] = extValue

        if 'EXT-X-PRIVINF' in self.extInfo.keys() and len(self.extInfo['EXT-X-PRIVINF']) > 0:
            self.tsList = [re.split(r',*\s+', item)[1] for item in self.extInfo['EXT-X-PRIVINF']]
        else:
            self.tsList = [re.split(r',*\s+', item)[1] for item in self.extInfo['EXTINF']]

        if 'EXT-X-KEY'in self.extInfo.keys():
            keyInfoList = self.extInfo['EXT-X-KEY'].split(',')
            for keyInfo in keyInfoList:
                key = keyInfo.split('=')[0]
                val = keyInfo.split('=')[1].replace('"', '')
                self.keyInfo[key] = val

            baseUrl = self.url[: self.url.rfind('/')+ 1]
            keyUrl = self.keyInfo['URI']

            if not self.is_http(keyUrl):
                keyUrl = self.url[: self.url.rfind('/')+ 1] + keyUrl
            self.key = requests.get(keyUrl ,headers={'User-Agent': random.choice(user_agent_list)}).text
        print(f'keyInfo is{self.keyInfo}, key is {self.key}, ts count is {len(self.tsList)}')


    @retry(wait_random_min = 2000,wait_random_max = 5000, stop_max_attempt_number = 3)
    def download_ts(self, filename):
        if not self.is_http(filename):
            tsUrl = self.url[: self.url.rfind('/')+ 1] + filename
        else:
            tsUrl = filename
            filename = urlparse(filename).path.split('/')[-1]

        #print(f'begin download  {tsUrl}')
        try:
            response = requests.get(tsUrl ,headers={'User-Agent': random.choice(user_agent_list)}, timeout=60)
            if self.key:
                if 'IV' in self.keyInfo.keys():
                    cryptor = AES.new(self.key, AES.MODE_CBC, self.keyInfo['IV'])
                else:
                    cryptor = AES.new(self.key, AES.MODE_CBC, self.key)
                outputContent=cryptor.decrypt(response.content)
            else:
                outputContent = response.content
            #TODO：需要处理tsfile是url的情况。需要从url截取url中的文件名作为保存文件名
            with open(self.workDir + '/' +filename, 'wb+') as f:
                f.write(outputContent)
            #print(f'finish download  {tsUrl}')
        except Exception as e:
            print(e)

    def download(self):
        if  os.path.exists(self.workDir):
            shutil.rmtree(self.workDir)
        os.mkdir(self.workDir)

        # for tsFile in self.tsList:
        #     self.download_ts(tsFile)
        
        with ThreadPoolExecutor(max_workers = self.poolSize) as t:
            #在主线程阻塞
            # all_task = [t.submit(self.download_ts, tsItem) for tsItem in self.tsList]
            # wait(all_task, return_when=ALL_COMPLETED)

            #as_completed() 方法是一个生成器，在没有任务完成的时候，会一直阻塞，除非设置了 timeout。当有某个任务完成的时候，会 yield 这个任务，就能执行 for 循环下面的语句，然后继续阻塞住，循环到所有的任务结束。同时，先完成的任务会先返回给主线程。
            obj_list = []
            finishCount = 0
            for tsItem in self.tsList:
                obj = t.submit(self.download_ts, tsItem)
                obj_list.append(obj)

            for future in as_completed(obj_list):
                #data = future.result()
                finishCount+=1
                print (f"\rdownload {self.url} ({finishCount}/{len(self.tsList)})", end="")
            
            print ("\ndownload finished ...")


    def merge_tsfile(self):
        '''
            直接拼接的可以播放，但是快进后退等会有问题
        '''
        fileList = os.listdir(self.workDir)
        fileList.sort()
        try:
            outFile =open(self.output, 'ab+')
            for tsFile in fileList:
                with open(os.path.join(self.workDir, tsFile), 'rb') as f:
                    content = f.read()
                    outFile.write(content)

            print(f'output file is {self.output}')

        except Exception as e:
            print(e)
        finally:
            outFile.close()

    def merge_tsfile_use_ffmpeg(self):
        print("开始合并文件")
        ffmpegFile = os.path.join(self.workDir, 'ffmpegFile.txt')
        #flieLines = [f"file  '{item}'\n" for item in self.tsList]
        flieLines =[]
        for item in self.tsList:
            if os.path.exists(os.path.join(self.workDir, item)):
                flieLines.append(f"file  '{item}'\n")
            else:
                print(f'waring %{item} do not exist, download failed')
        with open(ffmpegFile, 'w+') as f:
            f.writelines(flieLines)
        
        #ffmpeg -allowed_extensions ALL -protocol_whitelist "file,http,crypto,tcp,https" -i index.m3u8 -c copy out.mp4
        #ffmpeg -i "1.ts|2.ts|3.ts|4.ts|.5.ts|" -c copy output.mp4
        #ffmpeg -f concat -i filelist.txt -c copy output.mkv  file格式:file 'input1.mkv'
        if os.path.exists(ffmpegFile) and os.path.getsize(ffmpegFile)> 0:
            ffmpegCommand = f'ffmpeg -y -f concat -safe 0 -i {ffmpegFile} -c copy {self.output}'
            print(f'ffmpegCommand is {ffmpegCommand}')
            os.system(ffmpegCommand)
            print(f'output file is {self.output}')
        else:
            print(f'warning {ffmpegFile} do not exist or empty')


    def remove_work_dir(self):
        if  os.path.exists(self.workDir):
            shutil.rmtree(self.workDir)
    
    def run(self):
        startTime = time.time()
        self.get_m3u8_info()
        self.download()

        if self.ffmpegFlag:
            self.merge_tsfile_use_ffmpeg()
        else:
            self.merge_tsfile()
        self.remove_work_dir()
        print(f'total cost time {time.time() - startTime} s')

if __name__ == '__main__':

    parser = argparse.ArgumentParser(description="download video from m3u8")
    parser.add_argument('-u','--url',required=True ,help="m3u8 url")
    parser.add_argument('-o','--output', default="output.mp4", help="ouput video name, defult output.mp4")
    parser.add_argument('-t','--thread', type=int, default="20", help="thread num, default 20")
    parser.add_argument('--ffmpeg', action="store_true", default=True, help="use ffmpeg merge the ts file")
    args = parser.parse_args()
    
    downloader = M3u8Downloader(args.url, output= args.output, poolSize=args.thread, ffmpegFlag=args.ffmpeg)
    downloader.run()