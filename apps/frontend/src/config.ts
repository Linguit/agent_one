import type { PublicConfig } from './public-config'

/** 这里只接收构建时白名单投影后的公开字段。 */
export const config: Readonly<PublicConfig> = Object.freeze(__PUBLIC_CONFIG__)
