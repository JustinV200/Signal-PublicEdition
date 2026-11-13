// Root component: the store, then a gate on the session state.
import { StoreProvider, useStore } from "../state";
import type { HashLink } from "../state";
import { Shell } from "./Shell";
import { SignIn } from "./SignIn";

function Gate() {
  const { state } = useStore();
  if (state.auth === "out") return <SignIn />;
  // Nothing while the first login/state round trip is in flight (it is quick).
  if (state.auth === "checking") return null;
  return <Shell />;
}

/** The whole app, given the `#k=&v=&t=` link taken from the URL before render. */
export function App({ link }: { link: HashLink }) {
  return (
    <StoreProvider loginKey={link.key} startView={link.view} startTool={link.tool}>
      <Gate />
    </StoreProvider>
  );
}
