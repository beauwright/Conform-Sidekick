import { Separator } from "./components/ui/separator"

const licenses = () => {
    return (
        <div className="dark:text-white text-lg w-11/12 mx-auto pb-5">
            <h1 className="font-semibold text-xl">Conform Sidekick Copyright and License</h1>
            <p>Conform Sidekick - Copyright © 2024, Beau Wright. Conform Sidekick is made avaliable for use under the <a href="https://github.com/beauwright/Conform-Sidekick/blob/main/LICENSE" target="_blank" className="underline">GNU General Public License v3.0 license</a>.</p>
            <Separator className="my-2"/>
            <h2 className="font-semibold text-xl">Credits</h2>
            <p>Conform Sidekick is developed by Beau Wright and also relies on the hard work of several third-party open source projects:</p>
            <ul className="ml-7 list-disc">
                <li><a href="https://github.com/python-pillow/Pillow" target="_blank" className="underline">Pillow</a>  - Copyright © 2010-2024, Jeffrey A. Clark and contributors - used under the open source HPND License.</li>
                <li><a href="https://github.com/bigcat88/pillow_heif" target="_blank" className="underline">pillow-heif</a>  - Copyright © 2021-2023, Pillow-Heif contributors - used under the open source BSD-3-Clause license.</li>
                <li><a href="https://github.com/eoyilmaz/timecode" target="_blank" className="underline">timecode</a> - Copyright © 2014 Joshua Banton and PyTimeCode developers - used under the MIT License.</li>
                <li><a href="https://github.com/pyinstaller/pyinstaller" target="_blank" className="underline">pyinstaller</a> - Copyright © 2010-2024, PyInstaller Development Team - used under the GNU General Public License</li>
                <li><a href="https://github.com/facebook/react" target="_blank" className="underline">React</a> - Copyright (c) Meta Platforms, Inc. and affiliates - used under the MIT License.</li>
                <li><a href="https://github.com/tauri-apps/tauri" target="_blank" className="underline">Tauri</a> - Copyright (c) 2024 - Present Tauri Apps Contributors - used under the MIT License.</li>
                <li><a href="https://github.com/vitejs/vite" target="_blank" className="underline">Vite</a> - Copyright (c) 2019-present, Yuxi (Evan) You and Vite contributors - used under the MIT License.</li>
            </ul>
        </div>
    )
}

export default licenses