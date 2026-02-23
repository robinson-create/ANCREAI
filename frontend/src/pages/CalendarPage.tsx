/**
 * Calendar page - Main calendar interface.
 *
 * Features:
 * - 3-day calendar view
 * - Filters (provider, search)
 * - Event detail panel
 * - Create event dialog
 * - Connect provider CTA (if no providers)
 */

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Calendar, Filter, Link as LinkIcon } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { ThreeDayCalendarView } from '@/components/calendar/ThreeDayCalendarView';
import { EventDetailPanel } from '@/components/calendar/EventDetailPanel';
import { CreateEventDialog } from '@/components/calendar/CreateEventDialog';
import { calendarApi } from '@/api/calendar';
import { useCalendarStore } from '@/stores/calendarStore';
import { CalendarProvider } from '@/types/calendar';

export function CalendarPage() {
  const [showFilters, setShowFilters] = useState(false);
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [selectedEventId, setSelectedEventId] = useState<string | null>(null);

  const {
    rangeStart,
    rangeEnd,
    selectedProvider,
    searchQuery,
    setProvider,
    setSearchQuery,
    setDraftEvent,
    moveRangeBy,
  } = useCalendarStore();

  // Fetch providers
  const { data: providers, isLoading: loadingProviders } = useQuery({
    queryKey: ['calendar', 'providers'],
    queryFn: () => calendarApi.getProviders(),
  });

  // Fetch events
  const {
    data: eventsData,
    isLoading: loadingEvents,
    refetch: refetchEvents,
  } = useQuery({
    queryKey: ['calendar', 'events', rangeStart, rangeEnd, selectedProvider, searchQuery],
    queryFn: () =>
      calendarApi.getEvents({
        range_start: rangeStart.toISOString(),
        range_end: rangeEnd.toISOString(),
        provider: selectedProvider || undefined,
        query: searchQuery || undefined,
      }),
    enabled: !!providers?.providers.length, // Only fetch if providers connected
  });

  const handleEventClick = (eventId: string) => {
    setSelectedEventId(eventId);
  };

  const handleSlotClick = (start: Date, end: Date) => {
    setDraftEvent({ starts_at: start, ends_at: end });
    setShowCreateDialog(true);
  };

  const handleNavigate = (date: Date) => {
    // Update store range when navigating
    const daysDiff = Math.floor((date.getTime() - rangeStart.getTime()) / (1000 * 60 * 60 * 24));
    if (daysDiff !== 0) {
      moveRangeBy(daysDiff);
    }
  };

  // No providers connected CTA
  if (!loadingProviders && !providers?.providers.length) {
    return (
      <div className="flex flex-col items-center justify-center h-full p-8 text-center">
        <Calendar className="w-16 h-16 text-muted-foreground mb-4" />
        <h2 className="font-heading text-2xl font-semibold mb-2 text-foreground">Connecte ton calendrier</h2>
        <p className="text-sm text-muted-foreground mb-6 max-w-md font-body">
          Pour utiliser le calendrier Ancre, connecte Google Calendar ou Microsoft Outlook dans
          tes paramètres.
        </p>
        <Button asChild className="gap-2">
          <a href="/app/profile#integrations">
            <LinkIcon className="w-4 h-4" />
            Connecter un calendrier
          </a>
        </Button>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-border">
        <div>
          <h1 className="font-heading text-2xl font-bold text-foreground">Calendrier</h1>
          <p className="text-sm text-muted-foreground font-body">
            Vue 3 jours
            {providers?.has_google && ' · Google'}
            {providers?.has_google && providers?.has_microsoft && ' +'}
            {providers?.has_microsoft && ' Outlook'}
          </p>
        </div>

        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setShowFilters(!showFilters)}
            className={showFilters ? 'bg-accent/10' : '' + ' gap-2'}
          >
            <Filter className="w-4 h-4" />
            Filtres
          </Button>
        </div>
      </div>

      {/* Filters */}
      {showFilters && (
        <div className="flex items-center gap-4 p-4 bg-muted/20 border-b border-border">
          <div className="flex-1">
            <Input
              placeholder="Rechercher un événement..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="max-w-sm font-body"
            />
          </div>

          {providers && (providers.has_google || providers.has_microsoft) && (
            <Select
              value={selectedProvider || 'all'}
              onValueChange={(val) => setProvider(val === 'all' ? null : (val as CalendarProvider))}
            >
              <SelectTrigger className="w-[180px]">
                <SelectValue placeholder="Tous les calendriers" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Tous les calendriers</SelectItem>
                {providers.has_google && (
                  <SelectItem value={CalendarProvider.GOOGLE}>Google Calendar</SelectItem>
                )}
                {providers.has_microsoft && (
                  <SelectItem value={CalendarProvider.MICROSOFT}>Microsoft Outlook</SelectItem>
                )}
              </SelectContent>
            </Select>
          )}
        </div>
      )}

      {/* Main content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Calendar view */}
        <div className="flex-1 p-4">
          <ThreeDayCalendarView
            events={eventsData?.events || []}
            isLoading={loadingEvents}
            onEventClick={handleEventClick}
            onSlotClick={handleSlotClick}
            onNavigate={handleNavigate}
            defaultDate={rangeStart}
          />
        </div>

        {/* Event detail panel */}
        {selectedEventId && (
          <div className="w-96 border-l">
            <EventDetailPanel
              eventId={selectedEventId}
              events={eventsData?.events || []}
              onClose={() => setSelectedEventId(null)}
            />
          </div>
        )}
      </div>

      {/* Dialogs */}
      <CreateEventDialog
        open={showCreateDialog}
        onClose={() => setShowCreateDialog(false)}
        onSuccess={() => {
          refetchEvents();
          setShowCreateDialog(false);
        }}
        providers={providers?.providers || []}
      />
    </div>
  );
}
