import NotFoundMessage from '../components/NotFoundMessage';
import { useAppTheme } from '../theme/ThemeContext';

export default function NotFound() {
  const { theme } = useAppTheme();
  return <NotFoundMessage theme={theme} backTo="/" backLabel="Back to Calculator" />;
}
