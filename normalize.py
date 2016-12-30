from subprocess import call
import requests 
from HTMLParser import HTMLParser
import urlparse
import os
import boto3

_bucketName = "dtns-normalize"

class DtnsParser(HTMLParser):
    inItem = False
    inLink = False
    rssLinks = {}

    def handle_starttag(self, tag, attrs):
        if tag == "item":
            self.inItem = True
        
        if tag == "link" and self.inItem:
            self.inLink = True
            
    def handle_data(self, data):
        if self.inItem and self.inLink:
            if data not in self.rssLinks.keys():
                self.rssLinks[data] = ""
            self.inItem = False
            self.inLink = False

def normalizeAudio(fileName):
    baseName = os.path.splitext(fileName)[0]
    result = call(["sox", fileName, "{0}_normalized.wav".format(baseName), 
        "compand", "0.3,1", "6:-70,-60,-20", "-5", "-90", "0.2"])

    if result != 0:
        print("Failed to call SOX Command")
        exit(1)

def convertToWav(fileName):
    result = call(["lame", "--decode", fileName])
    if result != 0:
        print("Failed to call LAME command")
        exit(1)

def encodeToMp3(fileName):
    result = call(["lame", "-b", "96", fileName])
    if result != 0:
        print("Failed to encode to MP3")
        exit(1)
        
def downloadRss():
    dtnsUrl = os.environ.get("DTNS_FEED_URL")
    if not dtnsUrl:
        print("Set DTNS_FEED_URL to download DTNS RSS Feed")
        exit(1)

    return requests.get(dtnsUrl, timeout=5)

def getMp3FileNameFromUrl(url):
    return urlparse.urlsplit(url)[2].replace("/patreon.posts/", "")

def convertFile(mp3Url):
    print("Downloading file")
    
    resp = requests.get(mp3Url, timeout=5, stream = True)
    fileName = getMp3FileNameFromUrl(mp3Url) 

    with open(fileName, "wb") as f:
        for chunk in resp.iter_content(chunk_size=128):
            f.write(chunk)

    print("Converting to wav")
    convertToWav(fileName)

    baseFileName = os.path.splitext(os.path.basename(fileName))[0]

    print("normalizing audio")
    normalizeAudio("{0}.wav".format(baseFileName))

    encodeToMp3("{0}_normalized.wav".format(baseFileName))
    return "{0}_normalized.mp3".format(baseFileName)

def getExistingFiles():
    s3 = boto3.resource('s3')
    bucket = s3.Bucket(_bucketName)
    keys = []
    for key in bucket.objects.all():
        keys.append(key.key.replace('_normalized', ''))

    return keys
    
def uploadFile(fileName):
    s3 = boto3.resource("s3")
    fullPath = os.path.abspath(fileName)
    s3.Object(_bucketName, fileName).put(Body=open(fullPath, 'rb'))

def cleanUpLocalFiles():
    directory = "/home/jalexander/src/dtns-normalizer"
    test = os.listdir(directory)

    for item in test:
        if item.endswith(".wav") or item.endswith(".mp3"):
            os.remove(os.path.join(directory, item))

def main():
    r = downloadRss()
    p = DtnsParser()
    p.feed(r.text)
    existing = getExistingFiles()
    for rssFile in p.rssLinks.keys():
        rssName = getMp3FileNameFromUrl(rssFile)
        if rssName not in existing:
            print("convert file {0}".format(rssName))
            fileName =  convertFile(rssFile)
            print("Uploading File {0}".format(fileName))
            uploadFile(fileName)
            cleanUpLocalFiles()
        else:
            print("Found {0} in s3, do not reconvert".format(rssName))


if __name__ == "__main__":
    main()

