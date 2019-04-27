# -*- coding: utf-8 -*-
"""
Created on Sun Jul 15 01:05:58 2018

@author: Nzix
"""

import binascii, struct
import base64, json
import os, traceback

from Crypto.Cipher import AES
from Crypto.Util.strxor import strxor as XOR
from mutagen import mp3, flac, id3

def dump(input_path, output_path = None, skip = True):

    output_path = (lambda path, meta: os.path.splitext(path)[0] + '.' + meta['format']) if not output_path else output_path
    output_path = (lambda path, meta: path) if not callable(output_path) else output_path

    core_key = binascii.a2b_hex('687A4852416D736F356B496E62617857')
    meta_key = binascii.a2b_hex('2331346C6A6B5F215C5D2630553C2728')
    unpad = lambda s : s[0:-(s[-1] if type(s[-1]) == int else ord(s[-1]))]

    f = open(input_path, 'rb')

    # magic header
    header = f.read(8)
    assert binascii.b2a_hex(header) == b'4354454e4644414d'

    # key data
    f.seek(2, 1)
    key_length = f.read(4)
    key_length = struct.unpack('<I', bytes(key_length))[0]

    key_data = bytearray(f.read(key_length))
    key_data = bytes(bytearray([byte ^ 0x64 for byte in key_data]))

    cryptor = AES.new(core_key, AES.MODE_ECB)
    key_data = unpad(cryptor.decrypt(key_data))[17:]
    key_length = len(key_data)

    # S-box (standard RC4 Key-scheduling algorithm)
    key = bytearray(key_data)
    S = bytearray(range(256))
    j = 0

    for i in range(256):
        j = (j + S[i] + key[i % key_length]) & 0xFF
        S[i], S[j] = S[j], S[i]

    # meta data
    meta_length = f.read(4)
    meta_length = struct.unpack('<I', bytes(meta_length))[0]

    if meta_length:
        meta_data = bytearray(f.read(meta_length))
        meta_data = bytes(bytearray([byte ^ 0x63 for byte in meta_data]))
        meta_data = base64.b64decode(meta_data[22:])

        cryptor = AES.new(meta_key, AES.MODE_ECB)
        meta_data = unpad(cryptor.decrypt(meta_data)).decode('utf-8')[6:]
        meta_data = json.loads(meta_data)
    else:
        meta_data = {'format': 'flac' if os.fstat(f.fileno()).st_size > 1024 ** 2 * 16 else 'mp3'}

    # crc32
    crc32 = f.read(4)
    crc32 = struct.unpack('<I', bytes(crc32))[0]

    # album cover
    f.seek(5, 1)
    image_size = f.read(4)
    image_size = struct.unpack('<I', bytes(image_size))[0]
    image_data = f.read(image_size) if image_size else None

    # media data
    output_path = output_path(input_path, meta_data)
    if skip and os.path.exists(output_path): return

    data = f.read()
    f.close()

    # stream cipher (modified RC4 Pseudo-random generation algorithm)
    stream = [S[(S[i] + S[(i + S[i]) & 0xFF]) & 0xFF] for i in range(256)]
    stream = bytes(bytearray(stream * (len(data) // 256 + 1))[1:1 + len(data)])
    data = XOR(data, stream)

    m = open(output_path, 'wb')
    m.write(data)
    m.close()

    # media tag
    def embed(item, content):
        item.encoding = 0
        item.type = 3
        item.mime = 'image/png' if content[0:4] == binascii.a2b_hex('89504E47') else 'image/jpeg'
        item.data = content
    
    if image_data:
        if meta_data['format'] == 'flac':
            audio = flac.FLAC(output_path)
            image = flac.Picture()
            embed(image, image_data)
            audio.clear_pictures()
            audio.add_picture(image)
        elif meta_data['format'] == 'mp3':
            audio = mp3.MP3(output_path)
            image = id3.APIC()
            embed(image, image_data)
            audio.tags.add(image)
        audio.save()

    if meta_length:
        audio = flac.FLAC(output_path) if meta_data['format'] == 'flac' else mp3.EasyMP3(output_path)
        audio['title'] = meta_data['musicName']
        audio['album'] = meta_data['album']
        audio['artist'] = '/'.join([artist[0] for artist in meta_data['artist']])
        audio.save()
    
    return output_path

if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1:
        files = sys.argv[1:]
    else:
        files = [name for name in os.listdir('.') if os.path.splitext(name)[-1] == '.ncm']
    
    if sys.version[0] == '2':
        files = [path.decode(sys.stdin.encoding) for path in files]

    if not files:
        print('please input file path!')
        
    for path in files:
        try:
            dump(path)
            print(os.path.split(path)[-1])
        except Exception as e:
            print(traceback.format_exc())
            pass