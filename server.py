import argparse
import asyncio
import logging
import os

import aiofiles
from aiohttp import web

NUMBER_BYTES = 500 * 1024

logging.basicConfig(level=logging.INFO)

def configure_argument_parser():
    parser = argparse.ArgumentParser(description="Асинхронный микросервис на aiohttp для скачивания архивов фото")

    parser.add_argument(
        "-l",
        "--logging",
        action="store_true",
        help="Включение логирования"
    )

    parser.add_argument(
        "-d",
        "--directory",
        help="Путь к директории с файлами, по умолчанию test_photos",
        default='test_photos'
    )

    parser.add_argument(
        "-t",
        "--timeout",
        action="store_true",
        help="Включение задержки"
    )
    return parser


async def archive(request, timeout, directory):
    response = web.StreamResponse()
    response.headers['Content-Disposition'] = 'attachment; filename="archive.zip"'

    archive_hash = request.match_info['archive_hash']

    if not os.path.exists(os.path.join(directory, archive_hash)):
        raise web.HTTPNotFound(text='Архив не существует или был удален')

    process = None

    try:
        process = await asyncio.create_subprocess_exec('zip', '-r', '-', archive_hash,
                                                       stdout=asyncio.subprocess.PIPE, cwd=directory)
        await response.prepare(request)

        chunk = True
        while chunk:
            chunk = await process.stdout.read(NUMBER_BYTES)
            logging.info('Sending archive chunk..')
            await response.write(chunk)
            if timeout:
                await asyncio.sleep(5)
        return response

    except asyncio.CancelledError:
        logging.error('Download was interrupted')
        raise
    except IndexError:
        logging.error('IndexError')
    except SystemExit:
        logging.error('SystemExit')
    finally:
        if process.returncode != 0:
            await asyncio.create_subprocess_exec('kill', str(process.pid))


async def handle_index_page(request):
    async with aiofiles.open('index.html', mode='r') as index_file:
        index_contents = await index_file.read()
    return web.Response(text=index_contents, content_type='text/html')


if __name__ == '__main__':
    arg_parser = configure_argument_parser()
    args = arg_parser.parse_args()
    logging.info(f"Аргументы командной строки {args}")

    logging.disable(logging.INFO)
    logging.disable(not args.logging)

    app = web.Application()
    app.add_routes([
        web.get('/', handle_index_page),
        web.get('/archive/{archive_hash}/', lambda request: archive(request, args.timeout, args.directory)),
    ])
    web.run_app(app)
