/**
 * 3-day calendar view component using React Big Calendar.
 *
 * Features:
 * - Shows 3 consecutive days
 * - Event click handler
 * - Slot click handler (for creating new events)
 * - Provider-specific styling (Google = blue, Microsoft = purple)
 */

import { useMemo } from 'react';
import { Calendar as BigCalendar, dateFnsLocalizer, type Event } from 'react-big-calendar';
import { format, parse, startOfWeek, getDay } from 'date-fns';
import { fr } from 'date-fns/locale';
import 'react-big-calendar/lib/css/react-big-calendar.css';
import './calendar-styles.css';
import { Button } from '@/components/ui/button';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import type { EventSummary } from '@/types/calendar';
import ThreeDayView from './ThreeDayView';

const locales = { fr };
const localizer = dateFnsLocalizer({
  format,
  parse,
  startOfWeek: () => startOfWeek(new Date(), { locale: fr }),
  getDay,
  locales,
});

interface Props {
  events: EventSummary[];
  isLoading?: boolean;
  onEventClick: (eventId: string) => void;
  onSlotClick: (start: Date, end: Date) => void;
  onNavigate?: (date: Date) => void;
  defaultDate?: Date;
}

interface CalendarEvent extends Event {
  resource: EventSummary;
}

export function ThreeDayCalendarView({
  events,
  isLoading = false,
  onEventClick,
  onSlotClick,
  onNavigate,
  defaultDate = new Date(),
}: Props) {
  // Convert EventSummary → React Big Calendar format
  const calendarEvents: CalendarEvent[] = useMemo(() => {
    return events.map((event) => ({
      id: event.id,
      title: event.title,
      start: new Date(event.starts_at),
      end: new Date(event.ends_at),
      resource: event,
    }));
  }, [events]);

  const handleSelectEvent = (event: CalendarEvent) => {
    onEventClick(event.resource.id);
  };

  const handleSelectSlot = ({ start, end }: { start: Date; end: Date }) => {
    onSlotClick(start, end);
  };

  const handleNavigate = (date: Date) => {
    onNavigate?.(date);
  };

  const views = useMemo(
    () => ({
      threeDays: ThreeDayView,
    }),
    []
  );

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="flex flex-col items-center gap-2">
          <div className="animate-spin w-8 h-8 border-4 border-primary border-t-transparent rounded-full" />
          <p className="text-sm text-muted-foreground">Chargement du calendrier...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full calendar-container">
      <BigCalendar
        localizer={localizer}
        events={calendarEvents}
        defaultView={"threeDays" as "month"}
        views={views as Record<string, typeof ThreeDayView>}
        defaultDate={defaultDate}
        onSelectEvent={handleSelectEvent}
        onSelectSlot={handleSelectSlot}
        onNavigate={handleNavigate}
        selectable
        step={15} // 15-minute increments
        timeslots={4} // 4 slots per hour (15 min each)
        min={new Date(2026, 0, 1, 7, 0)} // Start at 7 AM
        max={new Date(2026, 0, 1, 21, 0)} // End at 9 PM
        eventPropGetter={(event: CalendarEvent) => {
          const provider = event.resource.provider;
          return {
            className: provider === 'google' ? 'event-google' : 'event-microsoft',
          };
        }}
        components={{
          toolbar: CustomToolbar,
          event: EventCard,
        }}
        messages={{
          today: "Aujourd'hui",
          previous: 'Précédent',
          next: 'Suivant',
          month: 'Mois',
          week: 'Semaine',
          day: 'Jour',
          agenda: 'Agenda',
          date: 'Date',
          time: 'Heure',
          event: 'Événement',
          noEventsInRange: 'Aucun événement dans cette période.',
        }}
      />
    </div>
  );
}

// Custom toolbar with 3-day navigation
function CustomToolbar({ onNavigate, label }: any) {
  return (
    <div className="flex items-center justify-between mb-4 pb-4 border-b">
      <h2 className="text-lg font-semibold">{label}</h2>

      <div className="flex gap-2">
        <Button variant="outline" size="sm" onClick={() => onNavigate('TODAY')}>
          Aujourd&apos;hui
        </Button>
        <div className="flex border rounded-md">
          <Button
            variant="ghost"
            size="sm"
            className="rounded-r-none border-r"
            onClick={() => onNavigate('PREV')}
          >
            <ChevronLeft className="w-4 h-4" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="rounded-l-none"
            onClick={() => onNavigate('NEXT')}
          >
            <ChevronRight className="w-4 h-4" />
          </Button>
        </div>
      </div>
    </div>
  );
}

// Event card with provider badge and video indicator
function EventCard({ event }: { event: CalendarEvent }) {
  const { resource } = event;
  const hasVideo = !!resource.video_conference_link;

  return (
    <div className="flex flex-col gap-0.5 p-1 h-full text-xs overflow-hidden">
      <div className="font-medium truncate">{event.title}</div>
      <div className="flex items-center gap-1 text-[10px] opacity-75">
        {hasVideo && <span>📹</span>}
        {resource.attendees && resource.attendees.length > 0 && (
          <span>👥 {resource.attendees.length}</span>
        )}
      </div>
    </div>
  );
}
