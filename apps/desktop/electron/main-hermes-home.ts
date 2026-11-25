// The Hermes home the desktop main process runs against, resolved once at boot.
// Resolving it here also registers it with the file-preview read guard, so the
// home's (and every profile's) credential stores are refused before any IPC
// read can be served.

import { lstatSync, readFileSync } from 'node:fs'
import path from 'node:path'

import { resolveDesktopHermesHome } from './data-paths'
import { directoryExists, fileExists } from './fs-probes'
import { setSensitiveHermesHome } from './hardening'
import { readWindowsUserEnvVar } from './windows-user-env'

interface DirectInstall {
  home: string
  sourceRoot: string
}

function readSmallFile(file: string): string | null {
  try {
    const stat = lstatSync(file)

    return stat.isFile() && stat.size <= 16_384 ? readFileSync(file, 'utf8') : null
  } catch {
    return null
  }
}

function directOmaInstall(home: string): DirectInstall | null {
  // Read the installer-generated POSIX wrapper without executing it or
  // depending on the GUI's PATH. Accept only the single-target shlex form.
  const wrapper = readSmallFile(path.join(home, '.local', 'bin', 'oma-agent'))
  const match = wrapper?.match(/^#!\/bin\/sh\nexec (?:([\w@%+=:,./-]+)|'((?:[^'\r\n\0]|'"'"')*)') "\$@"\n$/u)
  const target = match?.[1] ?? match?.[2]?.replaceAll("'\"'\"'", "'")
  const suffix = '/.hermes/bin/hermes'

  if (!target?.startsWith('/') || !target.endsWith(suffix)) {return null}
  const sourceRoot = target.slice(0, -suffix.length)

  if (!sourceRoot || !fileExists(target) || !fileExists(path.join(sourceRoot, 'hermes_cli', 'main.py'))) {return null}
  const data = readSmallFile(path.join(sourceRoot, '.hermes', 'install-home'))?.replace(/\n$/, '')

  if (!data?.startsWith('/') || /[\r\n\0]/u.test(data) || !directoryExists(data)) {return null}

  return { home: data, sourceRoot }
}

export function resolveMainHermesHome(home: string, allowDirectInstall = true): { home: string; sourceRoot: string | null } {
  const env = process.env

  const install = allowDirectInstall && process.platform !== 'win32' && !env.HERMES_DESKTOP_USER_DATA_DIR &&
    !env.HERMES_DATA_DIR_SUFFIX && !env.HERMES_DESKTOP_HERMES_ROOT && !env.HERMES_DESKTOP_HERMES &&
    !env.HERMES_DESKTOP_IGNORE_EXISTING ? directOmaInstall(home) : null

  const hermesHome = (env.HERMES_HOME ? null : install?.home) ?? resolveDesktopHermesHome({
    home,
    directoryExists,
    readWindowsHome: (): string | null => readWindowsUserEnvVar('HERMES_HOME')
  })

  setSensitiveHermesHome(hermesHome)

  return { home: hermesHome, sourceRoot: hermesHome === install?.home ? install.sourceRoot : null }
}

export function initializeMainHermesHome(home: string, allowDirectInstall: boolean): { home: string; activeRoot: string } {
  const resolved = resolveMainHermesHome(home, allowDirectInstall)

  if (resolved.sourceRoot && !process.env.HERMES_HOME) {
    process.env.HERMES_HOME = resolved.home
  }

  return { home: resolved.home, activeRoot: resolved.sourceRoot ?? path.join(resolved.home, 'hermes-agent') }
}
