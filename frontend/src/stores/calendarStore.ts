/**
 * Calendar state management with Zustand.
 *
 * Manages:
 * - Date range for 3-day view
 * - Filters (provider, search query)
 * - Draft commands (for clarification flow)
 * - Modal state
 */

import { create } from 'zustand';
import { addDays } from 'date-fns';
import type { CalendarProvider, CalendarCommand, EventSummary } from '@/types/calendar';

interface CalendarState {
  // ========== 3-day view range ==========
  rangeStart: Date;
  rangeEnd: Date;

  // ========== Filters ==========
  selectedProvider: CalendarProvider | null;
  searchQuery: string;

  // ========== Draft state (clarification flow) ==========
  draftCommand: CalendarCommand | null;
  draftEvent: { starts_at: Date; ends_at: Date } | null; // For quick create

  // ========== Modal state ==========
  calendarModalOpen: boolean;
  calendarModalMode: 'select-event' | 'select-slot';
  calendarModalEvents: EventSummary[];

  // ========== Actions ==========
  setRange: (start: Date, end: Date) => void;
  moveRangeBy: (days: number) => void;
  setProvider: (provider: CalendarProvider | null) => void;
  setSearchQuery: (query: string) => void;
  setDraftCommand: (command: CalendarCommand | null) => void;
  setDraftEvent: (event: { starts_at: Date; ends_at: Date } | null) => void;
  openCalendarModal: (mode: 'select-event' | 'select-slot', events?: EventSummary[]) => void;
  closeCalendarModal: () => void;
  reset: () => void;
}

const getInitialRange = (): { start: Date; end: Date } => {
  const start = new Date();
  start.setHours(0, 0, 0, 0);
  const end = addDays(start, 2);
  end.setHours(23, 59, 59, 999);
  return { start, end };
};

export const useCalendarStore = create<CalendarState>((set, get) => {
  const { start, end } = getInitialRange();

  return {
    // Initial state
    rangeStart: start,
    rangeEnd: end,
    selectedProvider: null,
    searchQuery: '',
    draftCommand: null,
    draftEvent: null,
    calendarModalOpen: false,
    calendarModalMode: 'select-slot',
    calendarModalEvents: [],

    // Actions
    setRange: (start, end) => set({ rangeStart: start, rangeEnd: end }),

    moveRangeBy: (days) => {
      const { rangeStart, rangeEnd } = get();
      const newStart = addDays(rangeStart, days);
      const newEnd = addDays(rangeEnd, days);
      set({ rangeStart: newStart, rangeEnd: newEnd });
    },

    setProvider: (provider) => set({ selectedProvider: provider }),

    setSearchQuery: (query) => set({ searchQuery: query }),

    setDraftCommand: (command) => set({ draftCommand: command }),

    setDraftEvent: (event) => set({ draftEvent: event }),

    openCalendarModal: (mode, events = []) =>
      set({
        calendarModalOpen: true,
        calendarModalMode: mode,
        calendarModalEvents: events,
      }),

    closeCalendarModal: () =>
      set({
        calendarModalOpen: false,
        calendarModalEvents: [],
      }),

    reset: () => {
      const { start, end } = getInitialRange();
      set({
        rangeStart: start,
        rangeEnd: end,
        selectedProvider: null,
        searchQuery: '',
        draftCommand: null,
        draftEvent: null,
        calendarModalOpen: false,
        calendarModalEvents: [],
      });
    },
  };
});
