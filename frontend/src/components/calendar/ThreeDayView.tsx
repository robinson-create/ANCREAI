/**
 * Custom 3-day view for React Big Calendar.
 *
 * Extends TimeGrid to show exactly 3 consecutive days.
 */

import React from 'react';
import { Navigate } from 'react-big-calendar';
import TimeGrid from 'react-big-calendar/lib/TimeGrid';
import { format, addDays } from 'date-fns';
import { fr } from 'date-fns/locale';

class ThreeDayView extends React.Component<any> {
  static navigate = (date: Date, action: string) => {
    switch (action) {
      case Navigate.PREVIOUS:
        return addDays(date, -3);
      case Navigate.NEXT:
        return addDays(date, 3);
      case Navigate.TODAY:
        return new Date();
      default:
        return date;
    }
  };

  static title = (date: Date) => {
    const start = date;
    const end = addDays(date, 2);
    return `${format(start, 'dd MMM', { locale: fr })} - ${format(end, 'dd MMM yyyy', { locale: fr })}`;
  };

  static range = (date: Date) => {
    const start = new Date(date);
    return [0, 1, 2].map((i) => addDays(start, i));
  };

  render() {
    const { date, ...props } = this.props;
    const range = ThreeDayView.range(date);

    return <TimeGrid {...props} range={range} eventOffset={15} />;
  }
}

export default ThreeDayView;
