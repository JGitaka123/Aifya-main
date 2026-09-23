/** Generic API success response wrapper. */
export interface ApiResponse<T> {
  data: T;
  message?: string;
}

/** Generic paginated response. */
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}
