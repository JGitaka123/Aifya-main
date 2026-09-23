import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { Patient } from "@aifya/shared";
import { PatientLookup } from "./PatientLookup";

const { mockUsePatientSearch } = vi.hoisted(() => ({
  mockUsePatientSearch: vi.fn(),
}));

vi.mock("next-intl", () => ({
  useTranslations: () => (key: string): string => key,
}));

vi.mock("@/hooks/usePatients", () => ({
  usePatientSearch: (...args: unknown[]) => mockUsePatientSearch(...args),
}));

const patient: Patient = {
  id: "f7a5e360-a243-4e06-b409-47b082ed3ff5",
  mrn: "AIF-00042",
  facility_id: "4cc024cd-a9b1-4052-85bb-16ce2380b5ee",
  first_name: "Amina",
  middle_name: null,
  last_name: "Otieno",
  date_of_birth: "1990-04-12",
  gender: "female",
  national_id: null,
  passport_number: null,
  phone_number: "+254700000042",
  alternate_phone: null,
  email: null,
  county: "Nairobi",
  sub_county: null,
  ward: null,
  village: null,
  postal_address: null,
  occupation: null,
  marital_status: null,
  next_of_kin_name: null,
  next_of_kin_phone: null,
  next_of_kin_relationship: null,
  insurance_provider: null,
  insurance_member_number: null,
  sha_number: null,
  blood_group: null,
  allergies: null,
  chronic_conditions: null,
  photo_url: null,
  created_at: "2026-07-22T10:00:00Z",
  updated_at: "2026-07-22T10:00:00Z",
};

describe("PatientLookup", () => {
  it("searches and returns the selected patient", () => {
    mockUsePatientSearch.mockReturnValue({
      data: { items: [patient], total: 1, page: 1, page_size: 8 },
      isLoading: false,
    });
    const onSelect = vi.fn();

    render(<PatientLookup value={null} onSelect={onSelect} required />);
    fireEvent.change(screen.getByPlaceholderText("placeholder"), { target: { value: "Amina" } });
    expect(mockUsePatientSearch).toHaveBeenLastCalledWith("Amina", 1, 8);
    fireEvent.click(screen.getByRole("button", { name: /Amina Otieno/ }));

    expect(onSelect).toHaveBeenCalledWith(patient);
  });

  it("shows patient identity and supports clearing", () => {
    mockUsePatientSearch.mockReturnValue({ data: undefined, isLoading: false });
    const onSelect = vi.fn();

    render(<PatientLookup value={patient} onSelect={onSelect} />);
    expect(screen.getByText("AIF-00042 · +254700000042")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "clear" }));

    expect(onSelect).toHaveBeenCalledWith(null);
  });
});
