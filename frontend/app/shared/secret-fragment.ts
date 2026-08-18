import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router";

export function useSecretFragment(): URLSearchParams {
  const location = useLocation();
  const navigate = useNavigate();
  const [parameters] = useState(() => {
    const parameters = new URLSearchParams(location.hash.replace(/^#/, ""));
    if (location.hash && window.location.hash === location.hash) {
      window.history.replaceState(
        window.history.state,
        "",
        `${window.location.pathname}${window.location.search}`,
      );
    }
    return parameters;
  });

  useEffect(() => {
    if (location.hash) navigate({ hash: "" }, { replace: true });
  }, [location.hash, navigate]);

  return parameters;
}
