"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { Search, Plus, Users } from "lucide-react";
import { Link } from "@/i18n/routing";
import { usePatientSearch } from "@/hooks/usePatients";
import { formatDate } from "@/lib/utils";
import { PageHeader } from "@/components/ui/PageHeader";
import { Avatar } from "@/components/ui/Avatar";
import { DataTable } from "@/components/ui/DataTable";

/**
 * Patient search and list page.
 * Supports offline access via cached IndexedDB data.
 * @returns Patient list page
 */
export default function PatientsPage() {
  const t = useTranslations("patients");
  const tc = useTranslations("common");
  const [searchQuery, setSearchQuery] = useState("");
  const [page, setPage] = useState(1);
  const pageSize = 20;

  const { data, isLoading } = usePatientSearch(
    searchQuery || undefined,
    page,
    pageSize
  );

  const totalPages = data ? Math.ceil(data.total / pageSize) : 0;

  return (
    <div className="mx-auto max-w-[1500px] animate-[fade-in_0.3s_ease-out] space-y-6 p-5 sm:p-6 lg:p-8">
      <PageHeader
        icon={Users}
        title={t("search")}
        breadcrumbs={[{ label: t("search") }]}
        actions={
          <Link
            href="/patients/register"
            className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow hover:bg-primary/90"
          >
            <Plus className="h-4 w-4" />
            {t("newPatient")}
          </Link>
        }
      />

      {/* Search bar */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => {
            setSearchQuery(e.target.value);
            setPage(1);
          }}
          placeholder={tc("searchPlaceholder")}
          className="w-full rounded-lg border border-border bg-background py-2.5 pl-10 pr-4 text-sm text-foreground shadow-sm transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent"
        />
      </div>

      {/* Results table */}
      <DataTable
        headers={[
          { label: t("patientId") },
          { label: t("firstName") },
          { label: t("lastName") },
          { label: t("gender"), className: "hidden md:table-cell" },
          { label: t("phoneNumber"), className: "hidden md:table-cell" },
          { label: t("dateOfBirth"), className: "hidden lg:table-cell" },
        ]}
        isLoading={isLoading}
        isEmpty={!data?.items.length}
        page={page}
        totalPages={totalPages}
        onPageChange={setPage}
        totalCount={data?.total}
        columnCount={6}
      >
        {data?.items.map((patient) => (
          <tr
            key={patient.id}
            className="cursor-pointer transition-colors hover:bg-muted/30"
          >
            <td className="px-4 py-3">
              <div className="flex items-center gap-2.5">
                <Avatar
                  name={patient.first_name + " " + patient.last_name}
                  size="sm"
                />
                <Link
                  href={`/patients/${patient.id}`}
                  className="font-mono text-primary hover:underline"
                >
                  {patient.mrn}
                </Link>
              </div>
            </td>
            <td className="px-4 py-3 text-foreground">
              {patient.first_name}
            </td>
            <td className="px-4 py-3 text-foreground">
              {patient.last_name}
            </td>
            <td className="hidden px-4 py-3 capitalize text-foreground md:table-cell">
              {patient.gender}
            </td>
            <td className="hidden px-4 py-3 text-muted-foreground md:table-cell">
              {patient.phone_number}
            </td>
            <td className="hidden px-4 py-3 text-muted-foreground lg:table-cell">
              {formatDate(patient.date_of_birth)}
            </td>
          </tr>
        ))}
      </DataTable>
    </div>
  );
}
