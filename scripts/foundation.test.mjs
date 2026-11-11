import assert from 'node:assert/strict'
import { existsSync, readFileSync, readdirSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { spawnSync } from 'node:child_process'
import test from 'node:test'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const json = (path) => JSON.parse(readFileSync(join(root, path), 'utf8'))

test('最终目录、包、锁文件及脚本存在', () => {
  for (const path of ['apps/backend', 'apps/frontend', 'packages/api-contracts', 'config',
    'infra', 'scripts', 'openspec', 'docs', 'apps/backend/uv.lock', 'package-lock.json',
    'apps/backend/src/super_ai/__init__.py', 'AGENTS.md']) assert.ok(existsSync(join(root, path)), path)
  const pkg = json('package.json')
  assert.deepEqual(pkg.workspaces, ['apps/frontend', 'packages/api-contracts', 'docs'])
  for (const prefix of ['contracts', 'frontend']) {
    for (const suffix of ['typecheck', 'test']) assert.ok(pkg.scripts[`${prefix}:${suffix}`])
  }
  for (const script of ['frontend:dev', 'frontend:build', 'docs:dev', 'docs:build',
    'frontend:security', 'foundation:test']) assert.ok(pkg.scripts[script])
  for (const workspace of ['apps/frontend', 'packages/api-contracts']) {
    const scripts = json(`${workspace}/package.json`).scripts
    assert.ok(scripts.typecheck && scripts.test)
  }
  assert.ok(json('packages/api-contracts/package.json').exports['.'].types)
})

test('真实配置、凭据和生成文件被忽略，模板不被忽略', () => {
  const paths = ['config/project.json', 'config/user.project.json', '.env', '.env.local',
    '.idea/workspace.xml', 'apps/backend/.venv/x', 'node_modules/x', 'apps/frontend/dist/x',
    'coverage/x', 'apps/backend/.pytest_cache/x', 'apps/backend/.ruff_cache/x',
    'apps/backend/src/super_ai/__pycache__/x', 'docs/.vitepress/cache/x',
    'docs/.vitepress/dist/x', 'apps/backend/var/x', 'test.sqlite', 'test.db-wal', 'test.log']
  for (const path of paths) {
    const result = spawnSync('git', ['check-ignore', '--no-index', path], { cwd: root, encoding: 'utf8' })
    assert.equal(result.status, 0, `${path}: ${result.stderr}`)
  }
  for (const path of ['config/project.template.json', 'config/user.project.template.json']) {
    assert.equal(spawnSync('git', ['check-ignore', '--no-index', path], { cwd: root }).status, 1)
    const check = (value) => {
      for (const [key, item] of Object.entries(value)) {
        if (/key|secret|password/i.test(key)) assert.equal(item, '', `${path}:${key}`)
        if (item !== null && typeof item === 'object') check(item)
      }
    }
    check(json(path))
  }
  const staged = spawnSync('git', ['diff', '--cached', '--name-only', '--',
    'config/project.json', 'config/user.project.json'], { cwd: root, encoding: 'utf8' })
  assert.equal(staged.status, 0)
  assert.equal(staged.stdout.trim(), '')
})

test('导入路径和基础设施边界', () => {
  const walk = (dir) => readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const path = join(dir, entry.name)
    return entry.isDirectory() ? walk(path) : [path]
  })
  for (const path of walk(join(root, 'apps/backend/src')).filter((p) => p.endsWith('.py'))) {
    assert.doesNotMatch(readFileSync(path, 'utf8'), /(?:from|import)\s+src\.super_ai/)
  }
  for (const path of walk(join(root, 'apps/frontend/src'))) {
    assert.doesNotMatch(readFileSync(path, 'utf8'), /(?:import|require).*?(?:user\.)?project\.json/)
  }
  for (const dir of ['apps/frontend/src', 'apps/frontend/build', 'apps/backend/src']) {
    for (const path of walk(join(root, dir)).filter((p) => /\.(py|ts|vue)$/.test(p))) {
      assert.doesNotMatch(readFileSync(path, 'utf8'), /process\.env|os\.environ|os\.getenv|import\.meta\.env/)
    }
  }
  assert.ok(existsSync(join(root, 'infra/README.md')))
  for (const path of ['app.Dockerfile', 'project.compose.json', 'infra/app.Dockerfile',
    'infra/project.compose.json']) assert.ok(!existsSync(join(root, path)))
})

test('未跟踪的新文件也满足 diff 空白规则', () => {
  const result = spawnSync('git', ['ls-files', '--others', '--exclude-standard', '-z', '--', '.'],
    { cwd: root, encoding: 'utf8' })
  assert.equal(result.status, 0)
  for (const path of result.stdout.split('\0').filter(Boolean)) {
    const content = readFileSync(join(root, path), 'utf8')
    assert.doesNotMatch(content, /[\t ]+\r?$/m, `${path} 行尾空白`)
    assert.ok(content.endsWith('\n'), `${path} 缺少末尾换行`)
  }
})


test('本地 Compose 服务白名单和废资产黑名单', () => {
  const composePath = 'infra/compose.yaml'
  const raw = readFileSync(join(root, composePath), 'utf8')
  const allowed = ['alertmanager', 'attu', 'etcd', 'milvus', 'minio']
  const declared = [...raw.split(/^volumes:/m)[0].matchAll(/^  ([\w-]+):$/gm)]
  assert.deepEqual(declared.map((match) => match[1]).sort(), allowed)
  assert.doesNotMatch(raw, /\$\{|env_file|dockerfile|build:|cls[-_]mcp[-_]server|cls[-_]?log|log[-_]upload|sop[-_ ]?seed/i)
  for (const template of ['project.template.json', 'user.project.template.json']) {
    assert.ok(!Object.hasOwn(json('config/' + template), 'docker'))
  }
  const tracked = spawnSync('git', ['ls-files', '--cached', '--others', '--exclude-standard', '-z'],
    { cwd: root, encoding: 'utf8' })
  assert.equal(tracked.status, 0)
  for (const path of tracked.stdout.split('\0')) {
    assert.doesNotMatch(path, /(?:^|\/)(?:app\.Dockerfile|project\.compose\.json)$/i)
  }
})

test('Docker Compose 解析、健康检查和依赖关系', (t) => {
  const probe = spawnSync('docker', ['compose', 'version'], { cwd: root, encoding: 'utf8' })
  if (probe.error?.code === 'ENOENT' || probe.status !== 0) {
    t.skip('Docker Compose CLI 不可用')
    return
  }
  const parsed = spawnSync('docker', ['compose', '-f', 'infra/compose.yaml', 'config', '--format', 'json'],
    { cwd: root, encoding: 'utf8' })
  assert.equal(parsed.status, 0, parsed.stderr)
  const { services, volumes } = JSON.parse(parsed.stdout)
  assert.deepEqual(Object.keys(services).sort(), ['alertmanager', 'attu', 'etcd', 'milvus', 'minio'])
  assert.deepEqual(Object.keys(volumes).sort(), [
    'alertmanager-data', 'etcd-data', 'milvus-data', 'minio-data',
  ])
  for (const service of Object.values(services)) {
    assert.ok(service.healthcheck.test.length > 0)
    assert.equal(service.build, undefined)
    assert.equal(service.env_file, undefined)
    assert.ok((service.ports ?? []).every((port) => port.host_ip === '127.0.0.1'))
  }
  const healthyDependencies = (service) => Object.entries(service.depends_on).map(([key, value]) => {
    assert.equal(value.condition, 'service_healthy')
    return key
  }).sort()
  assert.deepEqual(healthyDependencies(services.milvus), ['etcd', 'minio'])
  assert.deepEqual(healthyDependencies(services.attu), ['milvus'])
  assert.ok(services.alertmanager.ports.some((port) => port.target === 9093))
  assert.ok(services.alertmanager.volumes.some((volume) =>
    volume.target === '/etc/alertmanager/alertmanager.yml' && volume.read_only === true))
})
