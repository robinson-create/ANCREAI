/**
 * Calendar API client.
 *
 * Handles all calendar-related API calls.
 */

import { apiClient } from './client';
import type {
  CalendarParseRequest,
  CalendarParseResponse,
  CalendarExecuteRequest,
  CalendarResult,
  ProvidersListResponse,
  CalendarEventsResponse,
  AvailabilityResponse,
} from '@/types/calendar';

const BASE_PATH = '/calendar';

export const calendarApi = {
  /**
   * Parse user text into structured calendar command
   */
  parse: async (data: CalendarParseRequest): Promise<CalendarParseResponse> => {
    const response = await apiClient.post(`${BASE_PATH}/parse`, data);
    return response.data;
  },

  /**
   * Execute a validated calendar command
   */
  execute: async (data: CalendarExecuteRequest): Promise<CalendarResult> => {
    const response = await apiClient.post(`${BASE_PATH}/execute`, data);
    return response.data;
  },

  /**
   * List connected calendar providers
   */
  getProviders: async (): Promise<ProvidersListResponse> => {
    const response = await apiClient.get(`${BASE_PATH}/providers`);
    return response.data;
  },

  /**
   * List calendar events within a date range
   */
  getEvents: async (params: {
    range_start: string;
    range_end: string;
    provider?: string;
    query?: string;
  }): Promise<CalendarEventsResponse> => {
    const response = await apiClient.get(`${BASE_PATH}/events`, { params });
    return response.data;
  },

  /**
   * Get availability (busy/free slots) - Optional
   */
  getAvailability: async (params: {
    range_start: string;
    range_end: string;
    provider?: string;
    slot_duration_minutes?: number;
  }): Promise<AvailabilityResponse> => {
    const response = await apiClient.get(`${BASE_PATH}/availability`, { params });
    return response.data;
  },
};
