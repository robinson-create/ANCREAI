/**
 * Calendar Connect Provider CTA - Call-to-action to connect calendar.
 *
 * Shown when user tries to use calendar features but has no provider connected.
 */

import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Link as LinkIcon, Calendar } from 'lucide-react';

export function CalendarConnectProviderCTA() {
  return (
    <Card className="max-w-md">
      <CardHeader className="text-center pb-3">
        <div className="mx-auto w-12 h-12 rounded-full bg-muted flex items-center justify-center mb-3">
          <Calendar className="w-6 h-6 text-muted-foreground" />
        </div>
        <CardTitle className="text-base">Connecte ton calendrier</CardTitle>
        <CardDescription>
          Pour créer et gérer tes événements, connecte Google Calendar ou Microsoft Outlook.
        </CardDescription>
      </CardHeader>

      <CardContent className="flex flex-col gap-2">
        <Button asChild>
          <a href="/app/profile#integrations">
            <LinkIcon className="w-4 h-4 mr-2" />
            Connecter un calendrier
          </a>
        </Button>
      </CardContent>
    </Card>
  );
}
