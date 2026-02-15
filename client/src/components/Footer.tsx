import { Link } from 'react-router-dom';

export default function Footer() {
  return (
    <footer className="bg-zinc-900 border-t border-zinc-800 py-6 text-center text-zinc-500 text-sm">
      <p>&copy; {new Date().getFullYear()} Countrydle. All rights reserved.</p>
      <div className="mt-2 flex justify-center gap-4">
        <Link to="/privacy-policy" className="hover:text-zinc-300 transition-colors">Privacy Policy</Link>
        <Link to="/terms" className="hover:text-zinc-300 transition-colors">Terms of Service</Link>
        <Link to="/cookie-policy" className="hover:text-zinc-300 transition-colors">Cookie Policy</Link>
      </div>
    </footer>
  );
}
