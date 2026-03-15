export interface RegexTemplate {
  id: string
  name: string
  description: string
  pattern: string
  fields: string[]
}

export interface SearchRequest {
  template: string
  pattern?: string
  first_name?: string
  last_name?: string
  search_path: string
  threads: number
  max_filesize: string
  case_insensitive: boolean
  file_types?: string[]
  exclude_types?: string[]
}

export interface SearchMatch {
  file_path: string
  line_number: number
  line_content: string
  match_start: number
  match_end: number
}

export interface SearchProgress {
  type: 'progress'
  files_scanned: number
  total_files?: number
  current_file: string
  matches_found: number
  speed: number
  eta_seconds?: number
}

export interface SearchResult {
  type: 'result'
  match: SearchMatch
}

export interface SearchComplete {
  type: 'complete'
  total_matches: number
  files_scanned: number
  duration_seconds: number
}

export interface SearchError {
  type: 'error'
  message: string
}

export type WebSocketMessage = SearchProgress | SearchResult | SearchComplete | SearchError

export interface Stats {
  total_files: number
  total_lines: number
  total_size_bytes: number
  file_types: Record<string, number>
  largest_files: Array<{
    path: string
    size: number
    lines: number
  }>
}

export interface Config {
  search_path: string
  threads: number
  max_filesize: string
  available_templates: RegexTemplate[]
}
