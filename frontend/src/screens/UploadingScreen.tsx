import { Spinner } from "../components/Spinner";

export function UploadingScreen(): JSX.Element {
  return (
    <section className="screen uploading-screen">
      <Spinner label="Mixing your take with the instrumental..." />
    </section>
  );
}
